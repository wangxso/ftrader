"""风险管理模块"""

import logging
from typing import Optional, Dict, Tuple
from .exchange import BinanceExchange

logger = logging.getLogger(__name__)


class RiskManager:
    """风险管理类"""
    
    def __init__(self, exchange: BinanceExchange, config):
        """
        初始化风险管理器
        
        Args:
            exchange: 交易所实例
            config: 配置对象
        """
        self.exchange = exchange
        self.config = config
        self.initial_balance = 0.0
        self.entry_price = 0.0
        self.entry_balance = 0.0
        
    def set_initial_balance(self, balance: float):
        """
        设置初始余额
        
        Args:
            balance: 初始余额
        """
        self.initial_balance = balance
        logger.info(f"设置初始余额: {balance:.2f} USDT")
    
    def set_entry_price(self, price: float, balance: float):
        """
        设置开仓价格和余额
        
        Args:
            price: 开仓价格
            balance: 开仓时的余额
        """
        self.entry_price = price
        self.entry_balance = balance
        logger.info(f"设置开仓价格: {price:.2f}, 开仓余额: {balance:.2f} USDT")
    
    def check_stop_loss(self, current_price: float, side: str) -> bool:
        """
        检查是否触发止损
        
        Args:
            current_price: 当前价格
            side: 交易方向 'long' 或 'short'
            
        Returns:
            是否触发止损
        """
        if self.entry_price == 0:
            return False
        
        stop_loss_percent = self.config.stop_loss_percent / 100.0
        
        if side == 'long':
            # 做多：价格下跌超过止损百分比
            price_drop = (self.entry_price - current_price) / self.entry_price
            if price_drop >= stop_loss_percent:
                logger.warning(
                    f"触发止损！当前价格: {current_price:.2f}, "
                    f"开仓价格: {self.entry_price:.2f}, "
                    f"跌幅: {price_drop*100:.2f}%"
                )
                return True
        else:
            # 做空：价格上涨超过止损百分比
            price_rise = (current_price - self.entry_price) / self.entry_price
            if price_rise >= stop_loss_percent:
                logger.warning(
                    f"触发止损！当前价格: {current_price:.2f}, "
                    f"开仓价格: {self.entry_price:.2f}, "
                    f"涨幅: {price_rise*100:.2f}%"
                )
                return True
        
        return False
    
    def check_take_profit(self, current_price: float, side: str) -> bool:
        """
        检查是否触发止盈
        
        Args:
            current_price: 当前价格
            side: 交易方向 'long' 或 'short'
            
        Returns:
            是否触发止盈
        """
        if self.entry_price == 0:
            return False
        
        take_profit_percent = self.config.take_profit_percent / 100.0
        
        if side == 'long':
            # 做多：价格上涨超过止盈百分比
            price_rise = (current_price - self.entry_price) / self.entry_price
            if price_rise >= take_profit_percent:
                logger.info(
                    f"触发止盈！当前价格: {current_price:.2f}, "
                    f"开仓价格: {self.entry_price:.2f}, "
                    f"涨幅: {price_rise*100:.2f}%"
                )
                return True
        else:
            # 做空：价格下跌超过止盈百分比
            price_drop = (self.entry_price - current_price) / self.entry_price
            if price_drop >= take_profit_percent:
                logger.info(
                    f"触发止盈！当前价格: {current_price:.2f}, "
                    f"开仓价格: {self.entry_price:.2f}, "
                    f"跌幅: {price_drop*100:.2f}%"
                )
                return True
        
        return False
    
    def check_max_loss(self, current_balance: float) -> bool:
        """
        检查是否超过最大亏损限制
        
        Args:
            current_balance: 当前余额
            
        Returns:
            是否超过最大亏损
        """
        if self.initial_balance == 0:
            return False
        
        loss = self.initial_balance - current_balance
        loss_percent = (loss / self.initial_balance) * 100.0
        max_loss_percent = self.config.max_loss_percent
        
        if loss_percent >= max_loss_percent:
            logger.error(
                f"超过最大亏损限制！当前余额: {current_balance:.2f}, "
                f"初始余额: {self.initial_balance:.2f}, "
                f"亏损: {loss:.2f} USDT ({loss_percent:.2f}%)"
            )
            return True
        
        return False
    
    def should_close_position(self, current_price: float, current_balance: float, 
                             side: str) -> Tuple[bool, str]:
        """
        判断是否应该平仓
        
        Args:
            current_price: 当前价格
            current_balance: 当前余额
            side: 交易方向
            
        Returns:
            (是否平仓, 原因)
        """
        # 检查止损
        if self.check_stop_loss(current_price, side):
            return True, "止损"
        
        # 检查止盈
        if self.check_take_profit(current_price, side):
            return True, "止盈"
        
        # 检查最大亏损
        if self.check_max_loss(current_balance):
            return True, "最大亏损限制"
        
        return False, ""
    
    def get_risk_status(self, current_price: float, current_balance: float, 
                       side: str) -> Dict:
        """
        获取当前风险状态
        
        Args:
            current_price: 当前价格
            current_balance: 当前余额
            side: 交易方向
            
        Returns:
            风险状态字典
        """
        status = {
            'entry_price': self.entry_price,
            'current_price': current_price,
            'initial_balance': self.initial_balance,
            'current_balance': current_balance,
        }
        
        if self.entry_price > 0:
            if side == 'long':
                price_change = (current_price - self.entry_price) / self.entry_price * 100
            else:
                price_change = (self.entry_price - current_price) / self.entry_price * 100
            
            status['price_change_percent'] = price_change
        
        if self.initial_balance > 0:
            balance_change = current_balance - self.initial_balance
            balance_change_percent = (balance_change / self.initial_balance) * 100
            status['balance_change'] = balance_change
            status['balance_change_percent'] = balance_change_percent
        
        # 计算止损止盈价格
        if self.entry_price > 0:
            if side == 'long':
                status['stop_loss_price'] = self.entry_price * (1 - self.config.stop_loss_percent / 100)
                status['take_profit_price'] = self.entry_price * (1 + self.config.take_profit_percent / 100)
            else:
                status['stop_loss_price'] = self.entry_price * (1 + self.config.stop_loss_percent / 100)
                status['take_profit_price'] = self.entry_price * (1 - self.config.take_profit_percent / 100)
        
        return status

