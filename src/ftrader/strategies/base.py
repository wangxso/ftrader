"""策略基类"""

import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime
from ..exchange import BinanceExchange
from ..risk_manager import RiskManager

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """策略基类，所有策略必须继承此类"""
    
    def __init__(self, strategy_id: int, exchange: BinanceExchange, risk_manager: RiskManager, config: Dict[str, Any]):
        """
        初始化策略
        
        Args:
            strategy_id: 策略ID
            exchange: 交易所实例
            risk_manager: 风险管理器
            config: 策略配置字典
        """
        self.strategy_id = strategy_id
        self.exchange = exchange
        self.risk_manager = risk_manager
        self.config = config
        
        # 策略状态
        self.is_active = False
        self.is_running = False
        self.error_message: Optional[str] = None
        
        # 策略统计
        self.start_time: Optional[datetime] = None
        self.total_trades = 0
        self.win_trades = 0
        self.loss_trades = 0
        
        # 回调函数（用于通知策略管理器）
        self.on_status_change = None
        self.on_trade = None
        self.on_error = None
    
    @abstractmethod
    def get_name(self) -> str:
        """获取策略名称"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """获取策略描述"""
        pass
    
    @abstractmethod
    async def start(self) -> bool:
        """
        启动策略（异步）
        
        Returns:
            是否成功启动
        """
        pass
    
    @abstractmethod
    async def stop(self) -> bool:
        """
        停止策略（异步）
        
        Returns:
            是否成功停止
        """
        pass
    
    @abstractmethod
    async def run_once(self) -> bool:
        """
        执行一次策略检查（异步）
        
        Returns:
            是否继续运行
        """
        pass
    
    async def run(self):
        """
        运行策略主循环（异步）
        """
        if not await self.start():
            self._notify_error("策略启动失败")
            return
        
        self.is_running = True
        self.start_time = datetime.utcnow()
        self._notify_status_change("running")
        
        logger.info(f"策略 {self.get_name()} 开始运行")
        
        try:
            check_interval = self.config.get('monitoring', {}).get('check_interval', 5)
            
            while self.is_active and self.is_running:
                try:
                    should_continue = await self.run_once()
                    if not should_continue:
                        break
                except Exception as e:
                    logger.error(f"策略执行错误: {e}", exc_info=True)
                    self._notify_error(str(e))
                    # 继续运行，不中断
                
                await asyncio.sleep(check_interval)
                
        except asyncio.CancelledError:
            logger.info(f"策略 {self.get_name()} 被取消")
        except Exception as e:
            logger.error(f"策略运行错误: {e}", exc_info=True)
            self._notify_error(str(e))
        finally:
            self.is_running = False
            await self.stop()
            self._notify_status_change("stopped")
            logger.info(f"策略 {self.get_name()} 已停止")
    
    def pause(self):
        """暂停策略"""
        self.is_running = False
        self._notify_status_change("paused")
        logger.info(f"策略 {self.get_name()} 已暂停")
    
    def resume(self):
        """恢复策略"""
        if self.is_active:
            self.is_running = True
            self._notify_status_change("running")
            logger.info(f"策略 {self.get_name()} 已恢复")
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取策略状态
        
        Returns:
            状态字典
        """
        status = {
            'strategy_id': self.strategy_id,
            'name': self.get_name(),
            'is_active': self.is_active,
            'is_running': self.is_running,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'total_trades': self.total_trades,
            'win_trades': self.win_trades,
            'loss_trades': self.loss_trades,
            'error_message': self.error_message,
        }
        return status
    
    def _notify_status_change(self, status: str):
        """通知状态变化"""
        if self.on_status_change:
            try:
                self.on_status_change(self.strategy_id, status)
            except Exception as e:
                logger.error(f"状态变化回调错误: {e}")
    
    def _notify_trade(self, trade_data: Dict[str, Any]):
        """通知交易事件"""
        if self.on_trade:
            try:
                self.on_trade(self.strategy_id, trade_data)
            except Exception as e:
                logger.error(f"交易回调错误: {e}")
    
    def _notify_error(self, error_message: str):
        """通知错误"""
        self.error_message = error_message
        if self.on_error:
            try:
                self.on_error(self.strategy_id, error_message)
            except Exception as e:
                logger.error(f"错误回调错误: {e}")
        self._notify_status_change("error")
    
    def record_trade(self, trade_type: str, side: str, symbol: str, price: float, 
                    amount: float, order_id: Optional[str] = None, pnl: Optional[float] = None,
                    close_reason: Optional[str] = None):
        """
        记录交易
        
        Args:
            trade_type: 交易类型 (open/close/add)
            side: 交易方向 (long/short)
            symbol: 交易对
            price: 价格
            amount: 数量（USDT）
            order_id: 订单ID
            pnl: 盈亏（平仓时）
            close_reason: 平仓原因（止盈/止损/最大亏损限制，仅平仓时使用）
        """
        self.total_trades += 1
        if pnl is not None:
            if pnl > 0:
                self.win_trades += 1
            else:
                self.loss_trades += 1
        
        trade_data = {
            'trade_type': trade_type,
            'side': side,
            'symbol': symbol,
            'price': price,
            'amount': amount,
            'order_id': order_id,
            'pnl': pnl,
            'timestamp': datetime.utcnow().isoformat(),
        }
        
        # 如果是平仓，记录平仓原因
        if trade_type == 'close' and close_reason:
            trade_data['close_reason'] = close_reason
        
        self._notify_trade(trade_data)
