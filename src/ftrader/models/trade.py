"""交易相关数据模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum
from ..database import Base


class TradeType(str, enum.Enum):
    """交易类型"""
    OPEN = "open"  # 开仓
    CLOSE = "close"  # 平仓
    ADD = "add"  # 加仓


class TradeSide(str, enum.Enum):
    """交易方向"""
    LONG = "long"  # 做多
    SHORT = "short"  # 做空


class Trade(Base):
    """交易记录模型"""
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False, index=True)
    strategy_run_id = Column(Integer, ForeignKey("strategy_runs.id"), nullable=True, index=True)
    
    # 交易信息
    trade_type = Column(SQLEnum(TradeType), nullable=False)
    side = Column(SQLEnum(TradeSide), nullable=False)
    symbol = Column(String(50), nullable=False)
    
    # 价格和数量
    price = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)  # USDT数量
    contracts = Column(Float, nullable=True)  # 合约数量
    
    # 订单信息
    order_id = Column(String(100), nullable=True, index=True)
    exchange_order_id = Column(String(100), nullable=True)
    
    # 盈亏信息（平仓时计算）
    pnl = Column(Float, nullable=True)  # 盈亏金额
    pnl_percent = Column(Float, nullable=True)  # 盈亏百分比
    
    # 时间戳
    executed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # 关联关系
    strategy = relationship("Strategy", back_populates="trades")
    
    def __repr__(self):
        return f"<Trade(id={self.id}, strategy_id={self.strategy_id}, type='{self.trade_type}', side='{self.side}')>"
