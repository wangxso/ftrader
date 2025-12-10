"""马丁格尔策略模块（重构版）"""

import logging
import asyncio
from typing import Optional, Dict, List, Any
from .base import BaseStrategy
from ..exchange import BinanceExchange
from ..risk_manager import RiskManager

logger = logging.getLogger(__name__)


class MartingaleStrategy(BaseStrategy):
    """马丁格尔抄底策略"""
    
    def __init__(self, strategy_id: int, exchange: BinanceExchange, risk_manager: RiskManager, config: Dict[str, Any]):
        """
        初始化策略
        
        Args:
            strategy_id: 策略ID
            exchange: 交易所实例
            risk_manager: 风险管理器
            config: 配置字典
        """
        super().__init__(strategy_id, exchange, risk_manager, config)
        
        # 策略状态
        self.entry_price = 0.0
        self.highest_price = 0.0  # 做多时记录最高价，做空时记录最低价
        self.addition_count = 0
        self.positions: List[Dict] = []  # 记录所有加仓位置
        
        # 从配置中提取参数
        trading = config.get('trading', {})
        self.symbol = trading.get('symbol', 'BTC/USDT:USDT')
        self.side = 'buy' if trading.get('side', 'long') == 'long' else 'sell'
        self.position_side = trading.get('side', 'long')
        self.leverage = trading.get('leverage', 10)
        
        martingale = config.get('martingale', {})
        self.initial_position = martingale.get('initial_position', 200)
        self.multiplier = martingale.get('multiplier', 2.0)
        self.max_additions = martingale.get('max_additions', 5)
        
        trigger = config.get('trigger', {})
        self.price_drop_percent = trigger.get('price_drop_percent', 5.0)
        self.start_immediately = trigger.get('start_immediately', True)
        
        risk = config.get('risk', {})
        self.stop_loss_percent = risk.get('stop_loss_percent', 10.0)
        self.take_profit_percent = risk.get('take_profit_percent', 15.0)
        self.max_loss_percent = risk.get('max_loss_percent', 20.0)
    
    def get_name(self) -> str:
        """获取策略名称"""
        return "马丁格尔策略"
    
    def get_description(self) -> str:
        """获取策略描述"""
        return f"马丁格尔抄底策略 - {self.symbol} {self.position_side}"
    
    async def start(self) -> bool:
        """启动策略（异步）"""
        logger.info("=" * 60)
        logger.info("启动马丁格尔策略")
        logger.info(f"交易对: {self.symbol}")
        logger.info(f"方向: {self.position_side}")
        logger.info(f"杠杆: {self.leverage}x")
        logger.info(f"初始仓位: {self.initial_position} USDT")
        logger.info(f"加仓倍数: {self.multiplier}x")
        logger.info(f"最大加仓次数: {self.max_additions}")
        logger.info(f"触发下跌: {self.price_drop_percent}%")
        logger.info(f"立即开始: {'是' if self.start_immediately else '否'}")
        logger.info("=" * 60)
        
        # 设置杠杆（同步操作，在线程池中执行）
        loop = asyncio.get_event_loop()
        leverage_set = await loop.run_in_executor(
            None, 
            self.exchange.set_leverage, 
            self.symbol, 
            self.leverage
        )
        
        if not leverage_set:
            logger.error("设置杠杆失败，策略无法启动")
            if self.exchange.testnet:
                logger.info("提示：测试网需要有效的API密钥才能设置杠杆")
                logger.info("测试网API密钥申请地址: https://testnet.binancefuture.com/")
            return False
        
        # 获取初始余额
        balance = await loop.run_in_executor(None, self.exchange.get_balance)
        initial_balance = balance['total']
        self.risk_manager.set_initial_balance(initial_balance)
        
        self.is_active = True
        
        # 如果配置了立即开始，则立即开仓
        if self.start_immediately:
            logger.info("配置了立即开始，正在执行初始开仓...")
            current_price = await self.get_current_price()
            if current_price is None:
                logger.error("无法获取当前价格，无法立即开仓")
            else:
                # 记录当前价格作为参考价格
                self.highest_price = current_price
                size = self.calculate_position_size(0)
                if await self.open_position(size, current_price):
                    logger.info("立即开仓成功")
                    self.addition_count = 0
        
        return True
    
    async def stop(self) -> bool:
        """停止策略（异步）"""
        logger.info("停止策略")
        self.is_active = False
        return True
    
    async def get_current_price(self) -> Optional[float]:
        """获取当前价格（异步）"""
        loop = asyncio.get_event_loop()
        ticker = await loop.run_in_executor(None, self.exchange.get_ticker, self.symbol)
        if ticker:
            return ticker['last']
        return None
    
    def check_trigger_condition(self, current_price: float, reference_price: float) -> bool:
        """
        检查是否满足触发条件
        
        Args:
            current_price: 当前价格
            reference_price: 参考价格（最高价或最低价）
            
        Returns:
            是否触发
        """
        if reference_price == 0:
            return False
        
        price_drop_percent = self.price_drop_percent / 100.0
        
        if self.position_side == 'long':
            # 做多：价格从最高点下跌超过阈值
            drop = (reference_price - current_price) / reference_price
            return drop >= price_drop_percent
        else:
            # 做空：价格从最低点上涨超过阈值（反向触发）
            rise = (current_price - reference_price) / reference_price
            return rise >= price_drop_percent
    
    def calculate_position_size(self, addition_number: int) -> float:
        """
        计算加仓数量
        
        Args:
            addition_number: 加仓次数（0表示初始仓位）
            
        Returns:
            仓位大小（USDT）
        """
        if addition_number == 0:
            return self.initial_position
        
        # 马丁格尔：每次加仓 = 初始仓位 * (倍数 ^ 加仓次数)
        size = self.initial_position * (self.multiplier ** addition_number)
        return size
    
    async def open_position(self, size: float, price: float) -> bool:
        """
        开仓（异步）
        
        Args:
            size: 仓位大小（USDT）
            price: 开仓价格
            
        Returns:
            是否成功
        """
        try:
            loop = asyncio.get_event_loop()
            order = await loop.run_in_executor(
                None,
                self.exchange.create_market_order,
                self.symbol,
                self.side,
                size
            )
            
            if order:
                logger.info(
                    f"开仓成功: {self.position_side} {size:.2f} USDT "
                    f"@ {price:.2f} (订单ID: {order.get('id', 'N/A')})"
                )
                
                # 记录仓位
                position_info = {
                    'size': size,
                    'price': price,
                    'addition_number': self.addition_count,
                    'order_id': order.get('id'),
                }
                self.positions.append(position_info)
                
                # 更新开仓价格（加权平均）
                if self.entry_price == 0:
                    self.entry_price = price
                else:
                    # 计算新的平均价格
                    total_size = sum(p['size'] for p in self.positions)
                    weighted_price = sum(p['size'] * p['price'] for p in self.positions) / total_size
                    self.entry_price = weighted_price
                
                # 更新风险管理器的开仓价格
                balance = await loop.run_in_executor(None, self.exchange.get_balance)
                self.risk_manager.set_entry_price(self.entry_price, balance['total'])
                
                # 记录交易
                self.record_trade(
                    trade_type='open' if self.addition_count == 0 else 'add',
                    side=self.position_side,
                    symbol=self.symbol,
                    price=price,
                    amount=size,
                    order_id=str(order.get('id', ''))
                )
                
                return True
            else:
                logger.error("开仓失败：订单创建失败")
                return False
                
        except Exception as e:
            logger.error(f"开仓失败: {e}")
            return False
    
    def should_add_position(self, current_price: float) -> bool:
        """
        判断是否应该加仓
        
        Args:
            current_price: 当前价格
            
        Returns:
            是否应该加仓
        """
        # 检查是否达到最大加仓次数
        if self.addition_count >= self.max_additions:
            logger.warning(f"已达到最大加仓次数: {self.max_additions}")
            return False
        
        # 检查是否满足触发条件
        if self.highest_price == 0:
            # 首次触发，记录当前价格作为参考
            self.highest_price = current_price
            return True
        
        return self.check_trigger_condition(current_price, self.highest_price)
    
    def update_reference_price(self, current_price: float):
        """
        更新参考价格（最高价或最低价）
        
        Args:
            current_price: 当前价格
        """
        if self.position_side == 'long':
            # 做多：记录最高价
            if self.highest_price == 0 or current_price > self.highest_price:
                self.highest_price = current_price
        else:
            # 做空：记录最低价
            if self.highest_price == 0 or current_price < self.highest_price:
                self.highest_price = current_price
    
    async def run_once(self) -> bool:
        """
        执行一次策略检查（异步）
        
        Returns:
            是否继续运行
        """
        if not self.is_active:
            return False
        
        try:
            # 获取当前价格
            current_price = await self.get_current_price()
            if current_price is None:
                logger.warning("无法获取当前价格，跳过本次检查")
                return True
            
            # 更新参考价格
            self.update_reference_price(current_price)
            
            # 检查是否有持仓
            loop = asyncio.get_event_loop()
            position = await loop.run_in_executor(
                None,
                self.exchange.get_open_position,
                self.symbol
            )
            has_position = position is not None and position.get('contracts', 0) != 0
            
            if has_position:
                # 有持仓：检查止损止盈
                balance = await loop.run_in_executor(None, self.exchange.get_balance)
                should_close, reason = self.risk_manager.should_close_position(
                    current_price, balance['total'], self.position_side
                )
                
                if should_close:
                    logger.warning(f"触发平仓条件: {reason}")
                    closed = await loop.run_in_executor(
                        None,
                        self.exchange.close_position,
                        self.symbol
                    )
                    if closed:
                        logger.info("平仓成功")
                        
                        # 计算盈亏
                        pnl = balance['total'] - self.risk_manager.entry_balance if self.risk_manager.entry_balance > 0 else None
                        pnl_percent = None
                        if pnl is not None and self.risk_manager.entry_balance > 0:
                            pnl_percent = (pnl / self.risk_manager.entry_balance) * 100
                        
                        # 记录交易
                        self.record_trade(
                            trade_type='close',
                            side=self.position_side,
                            symbol=self.symbol,
                            price=current_price,
                            amount=0,  # 平仓时数量为0
                            pnl=pnl,
                            order_id=''
                        )
                        
                        self.is_active = False
                        return False
                    else:
                        logger.error("平仓失败")
                        return True
                
                # 检查是否可以加仓
                if self.should_add_position(current_price):
                    addition_number = self.addition_count + 1
                    size = self.calculate_position_size(addition_number)
                    
                    logger.info(
                        f"触发加仓条件 (第{addition_number}次加仓): "
                        f"当前价格 {current_price:.2f}, "
                        f"参考价格 {self.highest_price:.2f}, "
                        f"加仓大小 {size:.2f} USDT"
                    )
                    
                    if await self.open_position(size, current_price):
                        self.addition_count = addition_number
                        # 重置参考价格，等待下次触发
                        self.highest_price = current_price
                    else:
                        logger.error("加仓失败")
            else:
                # 无持仓：检查是否应该开仓
                if self.should_add_position(current_price):
                    logger.info(
                        f"触发开仓条件: 当前价格 {current_price:.2f}, "
                        f"参考价格 {self.highest_price:.2f}"
                    )
                    
                    size = self.calculate_position_size(0)
                    if await self.open_position(size, current_price):
                        self.addition_count = 0
                        self.highest_price = current_price
                    else:
                        logger.error("开仓失败")
            
            return True
            
        except Exception as e:
            logger.error(f"策略执行错误: {e}", exc_info=True)
            return True
