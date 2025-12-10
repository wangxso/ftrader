"""账户相关数据模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime
from ..database import Base


class AccountSnapshot(Base):
    """账户余额快照（用于收益曲线）"""
    __tablename__ = "account_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 余额信息
    total_balance = Column(Float, nullable=False)  # 总余额
    free_balance = Column(Float, nullable=False)  # 可用余额
    used_balance = Column(Float, nullable=False)  # 已用余额
    
    # 盈亏信息
    total_pnl = Column(Float, nullable=True)  # 总盈亏
    total_pnl_percent = Column(Float, nullable=True)  # 总盈亏百分比
    
    # 时间戳
    snapshot_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<AccountSnapshot(id={self.id}, balance={self.total_balance}, at={self.snapshot_at})>"
