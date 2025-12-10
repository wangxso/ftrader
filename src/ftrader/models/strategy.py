"""策略相关数据模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum
from ..database import Base


class StrategyType(str, enum.Enum):
    """策略类型"""
    CONFIG = "config"  # 配置型策略
    CODE = "code"  # 代码型策略


class StrategyStatus(str, enum.Enum):
    """策略状态"""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class Strategy(Base):
    """策略模型"""
    __tablename__ = "strategies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    strategy_type = Column(SQLEnum(StrategyType), nullable=False, default=StrategyType.CONFIG)
    
    # 配置型策略的YAML配置
    config_yaml = Column(Text, nullable=True)
    
    # 代码型策略的代码路径或代码内容
    code_path = Column(String(500), nullable=True)
    code_content = Column(Text, nullable=True)
    
    # 策略类名（用于代码型策略）
    class_name = Column(String(100), nullable=True)
    
    # 状态
    status = Column(SQLEnum(StrategyStatus), nullable=False, default=StrategyStatus.STOPPED)
    
    # 元数据
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # 关联关系
    runs = relationship("StrategyRun", back_populates="strategy", cascade="all, delete-orphan")
    trades = relationship("Trade", back_populates="strategy", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Strategy(id={self.id}, name='{self.name}', status='{self.status}')>"


class StrategyRun(Base):
    """策略运行记录"""
    __tablename__ = "strategy_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False, index=True)
    
    # 运行状态
    status = Column(SQLEnum(StrategyStatus), nullable=False, default=StrategyStatus.STOPPED)
    
    # 运行统计
    start_balance = Column(Float, nullable=True)  # 启动时余额
    current_balance = Column(Float, nullable=True)  # 当前余额
    total_trades = Column(Integer, default=0)  # 总交易次数
    win_trades = Column(Integer, default=0)  # 盈利交易次数
    loss_trades = Column(Integer, default=0)  # 亏损交易次数
    
    # 时间戳
    started_at = Column(DateTime, nullable=True)
    stopped_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # 错误信息
    error_message = Column(Text, nullable=True)
    
    # 关联关系
    strategy = relationship("Strategy", back_populates="runs")
    
    def __repr__(self):
        return f"<StrategyRun(id={self.id}, strategy_id={self.strategy_id}, status='{self.status}')>"
