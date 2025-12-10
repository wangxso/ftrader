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
from ..models.position import Position
from ..strategy_manager import get_strategy_manager
from ..exchange import BinanceExchange
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
    manager = get_strategy_manager()
    
    # 获取第一个交易所实例（所有策略共享同一个交易所）
    if manager.exchanges:
        exchange = list(manager.exchanges.values())[0]
    else:
        # 如果没有策略运行，创建默认交易所实例
        use_testnet = os.getenv('BINANCE_TESTNET', 'False').lower() == 'true'
        if use_testnet:
            api_key = os.getenv('BINANCE_TESTNET_API_KEY') or os.getenv('BINANCE_API_KEY', '')
            api_secret = os.getenv('BINANCE_TESTNET_SECRET_KEY') or os.getenv('BINANCE_SECRET_KEY', '')
        else:
            api_key = os.getenv('BINANCE_API_KEY', '')
            api_secret = os.getenv('BINANCE_SECRET_KEY', '')
        
        if not api_key or not api_secret:
            raise HTTPException(status_code=500, detail="未配置API密钥，无法获取余额")
        
        exchange = BinanceExchange(api_key, api_secret, testnet=use_testnet)
    
    balance = exchange.get_balance()
    
    return balance


@router.get("/positions", response_model=List[PositionResponse])
async def get_positions(db: Session = Depends(get_db)):
    """获取所有持仓"""
    positions = db.query(Position).filter(Position.is_closed == False).all()
    return positions


@router.get("/positions/{strategy_id}", response_model=List[PositionResponse])
async def get_strategy_positions(strategy_id: int, db: Session = Depends(get_db)):
    """获取指定策略的持仓"""
    positions = db.query(Position).filter(
        Position.strategy_id == strategy_id,
        Position.is_closed == False
    ).all()
    return positions


@router.get("/history", response_model=List[TradeResponse])
async def get_trade_history(
    strategy_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取交易历史"""
    query = db.query(Trade)
    
    if strategy_id:
        query = query.filter(Trade.strategy_id == strategy_id)
    
    trades = query.order_by(Trade.executed_at.desc()).offset(skip).limit(limit).all()
    return trades


@router.get("/snapshots")
async def get_account_snapshots(
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """获取账户余额快照（用于收益曲线）"""
    since = datetime.utcnow() - timedelta(hours=hours)
    
    snapshots = db.query(AccountSnapshot).filter(
        AccountSnapshot.snapshot_at >= since
    ).order_by(AccountSnapshot.snapshot_at.asc()).all()
    
    return [
        {
            'timestamp': s.snapshot_at.isoformat(),
            'balance': s.total_balance,
            'pnl': s.total_pnl,
            'pnl_percent': s.total_pnl_percent,
        }
        for s in snapshots
    ]


@router.get("/statistics")
async def get_account_statistics(db: Session = Depends(get_db)):
    """获取账户统计信息"""
    # 获取总交易数
    total_trades = db.query(Trade).count()
    
    # 获取盈利交易数
    win_trades = db.query(Trade).filter(Trade.pnl > 0).count()
    
    # 获取亏损交易数
    loss_trades = db.query(Trade).filter(Trade.pnl < 0).count()
    
    # 获取总盈亏
    total_pnl = db.query(func.sum(Trade.pnl)).scalar() or 0.0
    
    # 获取当前持仓数
    open_positions = db.query(Position).filter(Position.is_closed == False).count()
    
    # 获取当前余额
    manager = get_strategy_manager()
    balance = {'total': 0.0, 'free': 0.0, 'used': 0.0}
    if manager.exchanges:
        exchange = list(manager.exchanges.values())[0]
        balance = exchange.get_balance()
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
            try:
                exchange = BinanceExchange(api_key, api_secret, testnet=use_testnet)
                balance = exchange.get_balance()
            except Exception as e:
                logger.warning(f"获取余额失败: {e}")
    
    return {
        'total_balance': balance['total'],
        'free_balance': balance['free'],
        'used_balance': balance['used'],
        'total_trades': total_trades,
        'win_trades': win_trades,
        'loss_trades': loss_trades,
        'total_pnl': total_pnl,
        'win_rate': (win_trades / total_trades * 100) if total_trades > 0 else 0,
        'open_positions': open_positions,
    }
