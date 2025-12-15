"""回测相关数据模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
import enum
from ..database import Base


class BacktestStatus(str, enum.Enum):
    """回测状态"""
    PENDING = "pending"  # 等待中
    RUNNING = "running"  # 运行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败


class BacktestResult(Base):
    """回测结果模型"""
    __tablename__ = "backtest_results"
    
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False, index=True)
    
    # 回测配置
    start_date = Column(DateTime, nullable=False)  # 回测开始时间
    end_date = Column(DateTime, nullable=False)  # 回测结束时间
    initial_balance = Column(Float, nullable=False, default=10000.0)  # 初始余额
    symbol = Column(String(50), nullable=False)  # 交易对
    timeframe = Column(String(10), nullable=False, default='1m')  # 时间周期
    
    # 回测参数（JSON格式存储策略配置）
    parameters = Column(JSON, nullable=True)  # 回测时的策略参数
    
    # 回测结果
    final_balance = Column(Float, nullable=True)  # 最终余额
    total_return = Column(Float, nullable=True)  # 总收益率（百分比）
    total_return_amount = Column(Float, nullable=True)  # 总收益金额
    
    # 交易统计
    total_trades = Column(Integer, default=0, nullable=False)  # 总交易次数
    win_trades = Column(Integer, default=0, nullable=False)  # 盈利交易次数
    loss_trades = Column(Integer, default=0, nullable=False)  # 亏损交易次数
    win_rate = Column(Float, nullable=True)  # 胜率（百分比）
    
    # 风险指标
    max_drawdown = Column(Float, nullable=True)  # 最大回撤（百分比）
    max_drawdown_amount = Column(Float, nullable=True)  # 最大回撤金额
    sharpe_ratio = Column(Float, nullable=True)  # 夏普比率
    profit_factor = Column(Float, nullable=True)  # 盈亏比
    
    # 平均指标
    avg_win = Column(Float, nullable=True)  # 平均盈利
    avg_loss = Column(Float, nullable=True)  # 平均亏损
    avg_trade_return = Column(Float, nullable=True)  # 平均交易收益率
    
    # 详细数据（JSON格式）
    equity_curve = Column(JSON, nullable=True)  # 权益曲线数据
    trades_data = Column(JSON, nullable=True)  # 交易明细数据
    
    # 状态
    status = Column(SQLEnum(BacktestStatus), nullable=False, default=BacktestStatus.PENDING)
    error_message = Column(Text, nullable=True)  # 错误信息
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    # 关联关系
    strategy = relationship("Strategy", back_populates="backtest_results")
    
    def __repr__(self):
        return f"<BacktestResult(id={self.id}, strategy_id={self.strategy_id}, status='{self.status}')>"

