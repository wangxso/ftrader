"""账户管理API"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

import os
from ..database import get_db
from ..models.account import AccountSnapshot
from ..models.trade import Trade
from ..models.position import Position, PositionSide
from ..models.strategy import Strategy, StrategyType, StrategyStatus
from ..strategy_manager import get_strategy_manager
from ..exchange_manager import get_exchange
from dotenv import load_dotenv
from sqlalchemy import func

load_dotenv()

router = APIRouter(prefix="/api/account", tags=["account"])


class BalanceResponse(BaseModel):
    """余额响应"""
    total: float
    free: float
    used: float


class PositionResponse(BaseModel):
    """持仓响应"""
    id: int
    strategy_id: int
    symbol: str
    side: str
    entry_price: float
    current_price: Optional[float]
    contracts: float
    notional_value: float
    unrealized_pnl: Optional[float]
    unrealized_pnl_percent: Optional[float]
    leverage: int
    opened_at: datetime
    
    class Config:
        from_attributes = True


class TradeResponse(BaseModel):
    """交易响应"""
    id: int
    strategy_id: int
    trade_type: str
    side: str
    symbol: str
    price: float
    amount: float
    pnl: Optional[float]
    pnl_percent: Optional[float]
    executed_at: datetime
    
    class Config:
        from_attributes = True


@router.get("/balance", response_model=BalanceResponse)
async def get_balance():
    """获取账户余额"""
    try:
        # 使用单例管理器获取exchange实例
        exchange = get_exchange()
        balance = exchange.get_balance()
        if balance is None:
            # 余额获取失败，返回默认值但不应该触发风险检查
            logger.warning(f"获取账户余额失败，返回默认值")
            return {'total': 0.0, 'free': 0.0, 'used': 0.0}
        return balance
    except Exception as e:
        logger.warning(f"获取账户余额时发生错误: {e}，返回默认值")
        return {'total': 0.0, 'free': 0.0, 'used': 0.0}


@router.get("/positions", response_model=List[PositionResponse])
async def get_positions(db: Session = Depends(get_db)):
    """获取所有持仓"""
    try:
        # 先查询所有持仓（包括已平仓的）用于调试
        all_positions = db.query(Position).all()
        logger.info(f"数据库中总共有 {len(all_positions)} 个持仓（包括已平仓）")
        
        # 查询未平仓的持仓
        positions = db.query(Position).filter(Position.is_closed == False).all()
        logger.info(f"查询到 {len(positions)} 个未平仓的持仓")
        
        # 如果数据库中没有持仓记录，尝试从交易所同步
        if len(all_positions) == 0:
            logger.info("数据库中没有任何持仓记录，尝试从交易所同步持仓")
            try:
                exchange = get_exchange()
                exchange_positions = exchange.get_all_open_positions()
                
                if exchange_positions:
                    logger.info(f"从交易所获取到 {len(exchange_positions)} 个持仓，开始同步到数据库")
                    
                    # 获取或创建默认策略（用于存储交易所持仓）
                    default_strategy = db.query(Strategy).filter(Strategy.name == "交易所持仓").first()
                    if not default_strategy:
                        default_strategy = Strategy(
                            name="交易所持仓",
                            description="从交易所同步的实际持仓",
                            strategy_type=StrategyType.CONFIG,
                            status=StrategyStatus.STOPPED
                        )
                        db.add(default_strategy)
                        db.commit()
                        db.refresh(default_strategy)
                        logger.info(f"创建默认策略用于存储交易所持仓: {default_strategy.id}")
                    
                    # 同步每个持仓到数据库
                    for symbol, exchange_pos in exchange_positions.items():
                        try:
                            contracts = abs(exchange_pos.get('contracts', 0))
                            if contracts == 0:
                                continue
                            
                            # 确定持仓方向
                            side_str = exchange_pos.get('side', 'long')
                            if side_str in ['long', 'LONG']:
                                side = PositionSide.LONG
                            elif side_str in ['short', 'SHORT']:
                                side = PositionSide.SHORT
                            else:
                                # 根据合约数量正负判断
                                original_contracts = exchange_pos.get('contracts', 0)
                                side = PositionSide.LONG if original_contracts > 0 else PositionSide.SHORT
                            
                            # 获取价格信息
                            entry_price = exchange_pos.get('entryPrice') or exchange_pos.get('averagePrice') or 0.0
                            current_price = exchange_pos.get('markPrice') or exchange_pos.get('lastPrice') or entry_price
                            
                            # 计算名义价值
                            notional_value = abs(exchange_pos.get('notional', 0))
                            if notional_value == 0 and current_price > 0:
                                notional_value = contracts * current_price
                            
                            # 获取盈亏信息
                            unrealized_pnl = exchange_pos.get('unrealizedPnl')
                            unrealized_pnl_percent = exchange_pos.get('percentage')
                            
                            # 获取杠杆
                            leverage = exchange_pos.get('leverage', 1)
                            
                            # 检查是否已存在该持仓
                            existing = db.query(Position).filter(
                                Position.strategy_id == default_strategy.id,
                                Position.symbol == symbol,
                                Position.side == side,
                                Position.is_closed == False
                            ).first()
                            
                            if existing:
                                # 更新现有持仓
                                existing.entry_price = entry_price if entry_price > 0 else existing.entry_price
                                existing.current_price = current_price
                                existing.contracts = contracts
                                existing.notional_value = notional_value if notional_value > 0 else existing.notional_value
                                existing.unrealized_pnl = unrealized_pnl
                                existing.unrealized_pnl_percent = unrealized_pnl_percent
                                existing.leverage = leverage
                                existing.updated_at = datetime.utcnow()
                                logger.debug(f"更新持仓: {symbol} {side.value}")
                            else:
                                # 创建新持仓
                                position = Position(
                                    strategy_id=default_strategy.id,
                                    symbol=symbol,
                                    side=side,
                                    entry_price=entry_price if entry_price > 0 else current_price,
                                    current_price=current_price,
                                    contracts=contracts,
                                    notional_value=notional_value if notional_value > 0 else contracts * current_price,
                                    unrealized_pnl=unrealized_pnl,
                                    unrealized_pnl_percent=unrealized_pnl_percent,
                                    leverage=leverage,
                                    is_closed=False
                                )
                                db.add(position)
                                logger.info(f"创建新持仓: {symbol} {side.value} {contracts} 合约")
                        
                        except Exception as e:
                            logger.warning(f"同步持仓 {symbol} 失败: {e}", exc_info=True)
                            continue
                    
                    db.commit()
                    logger.info("持仓同步完成，重新查询数据库")
                    
                    # 重新查询数据库
                    positions = db.query(Position).filter(Position.is_closed == False).all()
                    logger.info(f"同步后查询到 {len(positions)} 个未平仓的持仓")
                else:
                    logger.info("交易所中也没有持仓")
            
            except Exception as e:
                logger.error(f"从交易所同步持仓失败: {e}", exc_info=True)
        
        # 如果查询结果为空，检查是否有已平仓的持仓
        if len(positions) == 0 and len(all_positions) > 0:
            closed_count = db.query(Position).filter(Position.is_closed == True).count()
            logger.info(f"所有持仓都已平仓（已平仓数量: {closed_count}）")
        
        # 转换为响应格式，确保枚举类型正确序列化
        result = []
        for pos in positions:
            try:
                # 确保side字段正确转换
                side_value = pos.side.value if hasattr(pos.side, 'value') else str(pos.side)
                logger.debug(f"处理持仓 {pos.id}: symbol={pos.symbol}, side={side_value}, is_closed={pos.is_closed}")
                
                result.append(PositionResponse(
                    id=pos.id,
                    strategy_id=pos.strategy_id,
                    symbol=pos.symbol,
                    side=side_value,
                    entry_price=pos.entry_price,
                    current_price=pos.current_price,
                    contracts=pos.contracts,
                    notional_value=pos.notional_value,
                    unrealized_pnl=pos.unrealized_pnl,
                    unrealized_pnl_percent=pos.unrealized_pnl_percent,
                    leverage=pos.leverage,
                    opened_at=pos.opened_at,
                ))
            except Exception as e:
                logger.error(f"序列化持仓 {pos.id} 失败: {e}", exc_info=True)
                continue
        
        logger.info(f"返回 {len(result)} 个持仓数据")
        return result
    except Exception as e:
        logger.error(f"获取持仓列表失败: {e}", exc_info=True)
        return []


@router.get("/positions/{strategy_id}", response_model=List[PositionResponse])
async def get_strategy_positions(strategy_id: int, db: Session = Depends(get_db)):
    """获取指定策略的持仓"""
    try:
        positions = db.query(Position).filter(
            Position.strategy_id == strategy_id,
            Position.is_closed == False
        ).all()
        logger.debug(f"查询到策略 {strategy_id} 的 {len(positions)} 个持仓")
        # 转换为响应格式，确保枚举类型正确序列化
        result = []
        for pos in positions:
            result.append(PositionResponse(
                id=pos.id,
                strategy_id=pos.strategy_id,
                symbol=pos.symbol,
                side=pos.side.value if hasattr(pos.side, 'value') else str(pos.side),
                entry_price=pos.entry_price,
                current_price=pos.current_price,
                contracts=pos.contracts,
                notional_value=pos.notional_value,
                unrealized_pnl=pos.unrealized_pnl,
                unrealized_pnl_percent=pos.unrealized_pnl_percent,
                leverage=pos.leverage,
                opened_at=pos.opened_at,
            ))
        return result
    except Exception as e:
        logger.error(f"获取策略持仓失败: {e}", exc_info=True)
        return []


@router.get("/history", response_model=List[TradeResponse])
async def get_trade_history(
    strategy_id: Optional[int] = None,
    strategy_run_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取交易历史"""
    try:
        query = db.query(Trade)
        
        if strategy_id:
            query = query.filter(Trade.strategy_id == strategy_id)
        
        # 如果指定了 strategy_run_id，只返回该运行记录的交易
        if strategy_run_id:
            query = query.filter(Trade.strategy_run_id == strategy_run_id)
        
        trades = query.order_by(Trade.executed_at.desc()).offset(skip).limit(limit).all()
        logger.debug(f"查询到 {len(trades)} 条交易记录 (strategy_id={strategy_id}, strategy_run_id={strategy_run_id}, skip={skip}, limit={limit})")
        return trades
    except Exception as e:
        logger.error(f"获取交易历史失败: {e}", exc_info=True)
        return []


@router.get("/snapshots")
async def get_account_snapshots(
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """获取账户余额快照（用于收益曲线）"""
    try:
        since = datetime.utcnow() - timedelta(hours=hours)
        
        snapshots = db.query(AccountSnapshot).filter(
            AccountSnapshot.snapshot_at >= since
        ).order_by(AccountSnapshot.snapshot_at.asc()).all()
        
        logger.debug(f"查询到 {len(snapshots)} 个账户快照 (hours={hours})")
        
        return [
            {
                'timestamp': s.snapshot_at.isoformat(),
                'balance': s.total_balance,
                'pnl': s.total_pnl,
                'pnl_percent': s.total_pnl_percent,
            }
            for s in snapshots
        ]
    except Exception as e:
        logger.error(f"获取账户快照失败: {e}", exc_info=True)
        return []


@router.get("/statistics")
async def get_account_statistics(db: Session = Depends(get_db)):
    """获取账户统计信息"""
    import asyncio
    
    # 先获取快速数据（数据库查询）
    total_trades = db.query(Trade).count()
    win_trades = db.query(Trade).filter(Trade.pnl > 0).count()
    loss_trades = db.query(Trade).filter(Trade.pnl < 0).count()
    total_pnl = db.query(func.sum(Trade.pnl)).scalar() or 0.0
    open_positions = db.query(Position).filter(Position.is_closed == False).count()
    
    # 默认余额值
    balance = {'total': 0.0, 'free': 0.0, 'used': 0.0}
    
    # 异步获取余额（不阻塞响应）
    async def fetch_balance():
        try:
            manager = get_strategy_manager()
            if manager.exchanges:
                exchange = list(manager.exchanges.values())[0]
                # 在后台线程中执行同步调用
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, exchange.get_balance)
                return result if result else balance
            else:
                # 如果没有策略运行，创建默认交易所实例
                use_testnet = os.getenv('BINANCE_TESTNET', 'False').lower() == 'true'
                if use_testnet:
                    api_key = os.getenv('BINANCE_TESTNET_API_KEY') or os.getenv('BINANCE_API_KEY', '')
                    api_secret = os.getenv('BINANCE_TESTNET_SECRET_KEY') or os.getenv('BINANCE_SECRET_KEY', '')
                else:
                    api_key = os.getenv('BINANCE_API_KEY', '')
                    api_secret = os.getenv('BINANCE_SECRET_KEY', '')
                
                if api_key and api_secret:
                    loop = asyncio.get_event_loop()
                    # 使用单例管理器获取exchange实例
                    from ..exchange_manager import get_exchange
                    exchange = await loop.run_in_executor(None, get_exchange)
                    result = await loop.run_in_executor(None, exchange.get_balance)
                    return result if result else balance
        except Exception as e:
            logger.warning(f"获取余额失败: {e}")
        return balance
    
    # 使用超时获取余额，如果超时则使用默认值
    try:
        balance = await asyncio.wait_for(fetch_balance(), timeout=2.0)
    except asyncio.TimeoutError:
        logger.warning("获取余额超时，使用默认值")
        balance = {'total': 0.0, 'free': 0.0, 'used': 0.0}
    except Exception as e:
        logger.warning(f"获取账户余额时发生错误: {e}，将使用默认值0")
        balance = {'total': 0.0, 'free': 0.0, 'used': 0.0}
    
    return {
        'total_balance': balance['total'] if balance else 0.0,
        'free_balance': balance.get('free', 0.0) if balance else 0.0,
        'used_balance': balance.get('used', 0.0) if balance else 0.0,
        'total_trades': total_trades,
        'win_trades': win_trades,
        'loss_trades': loss_trades,
        'total_pnl': total_pnl,
        'win_rate': (win_trades / total_trades * 100) if total_trades > 0 else 0,
        'open_positions': open_positions,
    }


class MarketOrderRequest(BaseModel):
    """市价单请求"""
    symbol: str
    side: str  # 'buy' 或 'sell'
    amount: float  # USDT数量
    reduce_only: bool = False


class LimitOrderRequest(BaseModel):
    """限价单请求"""
    symbol: str
    side: str  # 'buy' 或 'sell'
    amount: float  # USDT数量
    price: float  # 限价价格
    reduce_only: bool = False


class ClosePositionRequest(BaseModel):
    """平仓请求"""
    symbol: str


@router.post("/market-order")
async def create_market_order(request: MarketOrderRequest):
    """创建市价订单"""
    try:
        # 使用单例管理器获取exchange实例
        exchange = get_exchange()
        
        order = exchange.create_market_order(
            request.symbol,
            request.side,
            request.amount,
            reduce_only=request.reduce_only
        )
        
        if not order:
            raise HTTPException(status_code=400, detail="创建市价订单失败")
        
        return {
            'success': True,
            'order_id': order.get('id'),
            'status': order.get('status'),
            'symbol': order.get('symbol'),
            'side': order.get('side'),
            'amount': order.get('amount'),
            'price': order.get('price'),
            'filled': order.get('filled'),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建市价订单失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建市价订单失败: {str(e)}")


@router.post("/limit-order")
async def create_limit_order(request: LimitOrderRequest):
    """创建限价订单"""
    try:
        # 使用单例管理器获取exchange实例
        exchange = get_exchange()
        
        order = exchange.create_limit_order(
            request.symbol,
            request.side,
            request.amount,
            request.price,
            reduce_only=request.reduce_only
        )
        
        if not order:
            raise HTTPException(status_code=400, detail="创建限价订单失败")
        
        return {
            'success': True,
            'order_id': order.get('id'),
            'status': order.get('status'),
            'symbol': order.get('symbol'),
            'side': order.get('side'),
            'amount': order.get('amount'),
            'price': order.get('price'),
            'filled': order.get('filled'),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建限价订单失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建限价订单失败: {str(e)}")


@router.post("/close-position")
async def close_position(request: ClosePositionRequest):
    """平仓"""
    try:
        # 使用单例管理器获取exchange实例
        exchange = get_exchange()
        
        # 检查持仓
        position = exchange.get_open_position(request.symbol)
        
        if not position:
            return {
                'success': True,
                'message': '没有持仓，无需平仓'
            }
        
        success = exchange.close_position(request.symbol)
        
        if not success:
            raise HTTPException(status_code=400, detail="平仓失败")
        
        return {
            'success': True,
            'message': '平仓成功'
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"平仓失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"平仓失败: {str(e)}")


@router.get("/positions/debug")
async def debug_positions(db: Session = Depends(get_db)):
    """调试端点：查看数据库中的持仓数据"""
    try:
        all_positions = db.query(Position).all()
        closed_positions = db.query(Position).filter(Position.is_closed == True).all()
        open_positions = db.query(Position).filter(Position.is_closed == False).all()
        
        return {
            "total": len(all_positions),
            "closed": len(closed_positions),
            "open": len(open_positions),
            "all_positions": [
                {
                    "id": p.id,
                    "strategy_id": p.strategy_id,
                    "symbol": p.symbol,
                    "side": str(p.side),
                    "is_closed": p.is_closed,
                    "entry_price": p.entry_price,
                    "contracts": p.contracts,
                    "opened_at": p.opened_at.isoformat() if p.opened_at else None,
                }
                for p in all_positions
            ]
        }
    except Exception as e:
        logger.error(f"调试持仓数据失败: {e}", exc_info=True)
        return {"error": str(e)}