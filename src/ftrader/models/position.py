"""持仓相关数据模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum
from ..database import Base


class PositionSide(str, enum.Enum):
    """持仓方向"""
    LONG = "long"  # 做多
    SHORT = "short"  # 做空


class Position(Base):
    """持仓记录模型"""
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False, index=True)
    
    # 持仓信息
    symbol = Column(String(50), nullable=False, index=True)
    side = Column(SQLEnum(PositionSide), nullable=False)
    
    # 价格和数量
    entry_price = Column(Float, nullable=False)  # 开仓价格（加权平均）
    current_price = Column(Float, nullable=True)  # 当前价格
    contracts = Column(Float, nullable=False)  # 合约数量
    notional_value = Column(Float, nullable=False)  # 名义价值（USDT）
    
    # 盈亏信息
    unrealized_pnl = Column(Float, nullable=True)  # 未实现盈亏
    unrealized_pnl_percent = Column(Float, nullable=True)  # 未实现盈亏百分比
    
    # 杠杆
    leverage = Column(Integer, nullable=False, default=1)
    
    # 时间戳
    opened_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    closed_at = Column(DateTime, nullable=True)
    
    # 是否已平仓
    is_closed = Column(Boolean, default=False, nullable=False, index=True)
    
    def __repr__(self):
        return f"<Position(id={self.id}, strategy_id={self.strategy_id}, symbol='{self.symbol}', side='{self.side}')>"
