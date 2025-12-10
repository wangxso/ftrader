"""后台任务模块"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models.account import AccountSnapshot
from .strategy_manager import get_strategy_manager

logger = logging.getLogger(__name__)


class BackgroundTasks:
    """后台任务管理器"""
    
    def __init__(self):
        self.is_running = False
        self.task: Optional[asyncio.Task] = None
    
    async def start(self):
        """启动后台任务"""
        if self.is_running:
            return
        
        self.is_running = True
        self.task = asyncio.create_task(self._run_snapshots())
        logger.info("后台任务已启动")
    
    async def stop(self):
        """停止后台任务"""
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("后台任务已停止")
    
    async def _run_snapshots(self):
        """运行账户快照任务"""
        while self.is_running:
            try:
                await self._save_account_snapshot()
                await asyncio.sleep(60)  # 每分钟保存一次快照
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"保存账户快照失败: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _save_account_snapshot(self):
        """保存账户快照"""
        manager = get_strategy_manager()
        
        if not manager.exchanges:
            return
        
        # 获取第一个交易所实例
        exchange = list(manager.exchanges.values())[0]
        balance = exchange.get_balance()
        
        # 计算总盈亏（需要初始余额，这里简化处理）
        db = SessionLocal()
        try:
            # 获取最近的快照作为参考
            last_snapshot = db.query(AccountSnapshot).order_by(
                AccountSnapshot.snapshot_at.desc()
            ).first()
            
            total_pnl = None
            total_pnl_percent = None
            
            if last_snapshot:
                total_pnl = balance['total'] - last_snapshot.total_balance
                if last_snapshot.total_balance > 0:
                    total_pnl_percent = (total_pnl / last_snapshot.total_balance) * 100
            
            snapshot = AccountSnapshot(
                total_balance=balance['total'],
                free_balance=balance['free'],
                used_balance=balance['used'],
                total_pnl=total_pnl,
                total_pnl_percent=total_pnl_percent,
                snapshot_at=datetime.utcnow()
            )
            
            db.add(snapshot)
            db.commit()
            
        except Exception as e:
            logger.error(f"保存账户快照失败: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()


# 全局后台任务实例
_background_tasks: Optional[BackgroundTasks] = None


def get_background_tasks() -> BackgroundTasks:
    """获取后台任务管理器单例"""
    global _background_tasks
    if _background_tasks is None:
        _background_tasks = BackgroundTasks()
    return _background_tasks
