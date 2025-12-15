"""WebSocket API"""

import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import logging

from ..strategy_manager import get_strategy_manager

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """接受WebSocket连接"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket连接已建立，当前连接数: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """断开WebSocket连接"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket连接已断开，当前连接数: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """发送个人消息"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"发送WebSocket消息失败: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: str):
        """广播消息给所有连接"""
        disconnected = []
        for connection in self.active_connections:
            try:
                # 检查连接状态
                if connection.client_state.name == 'DISCONNECTED':
                    disconnected.append(connection)
                    continue
                await connection.send_text(message)
            except RuntimeError as e:
                # 连接已关闭或响应已完成
                error_msg = str(e)
                if 'websocket.close' in error_msg or 'response already completed' in error_msg:
                    logger.debug(f"连接已关闭，跳过消息发送: {e}")
                else:
                    logger.warning(f"广播消息失败: {e}")
                disconnected.append(connection)
            except Exception as e:
                logger.warning(f"广播消息失败: {e}")
                disconnected.append(connection)
        
        # 清理断开的连接
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


def broadcast_strategy_status(strategy_id: int, status: str):
    """广播策略状态变化"""
    message = {
        'type': 'strategy_status',
        'strategy_id': strategy_id,
        'status': status,
    }
    asyncio.create_task(manager.broadcast(json.dumps(message)))


def broadcast_trade(strategy_id: int, trade_data: Dict[str, Any]):
    """广播交易事件"""
    message = {
        'type': 'trade',
        'strategy_id': strategy_id,
        'data': trade_data,
    }
    asyncio.create_task(manager.broadcast(json.dumps(message)))


def broadcast_error(strategy_id: int, error_message: str):
    """广播错误事件"""
    message = {
        'type': 'error',
        'strategy_id': strategy_id,
        'error': error_message,
    }
    asyncio.create_task(manager.broadcast(json.dumps(message)))


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket端点"""
    await manager.connect(websocket)
    
    # 注册策略管理器的回调
    strategy_manager = get_strategy_manager()
    strategy_manager.register_callbacks(
        on_status_change=broadcast_strategy_status,
        on_trade=broadcast_trade,
        on_error=broadcast_error
    )
    
    try:
        # 发送初始数据
        initial_data = {
            'type': 'connected',
            'message': 'WebSocket连接成功',
        }
        await websocket.send_text(json.dumps(initial_data))
        
        # 保持连接
        while True:
            # 接收客户端消息（心跳等）
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # 可以处理客户端发送的消息
                message = json.loads(data)
                if message.get('type') == 'ping':
                    await websocket.send_text(json.dumps({'type': 'pong'}))
            except asyncio.TimeoutError:
                # 发送心跳
                await websocket.send_text(json.dumps({'type': 'heartbeat'}))
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket错误: {e}", exc_info=True)
        manager.disconnect(websocket)
