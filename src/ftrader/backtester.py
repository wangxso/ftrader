"""回测引擎模块"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from decimal import Decimal
import math

from .exchange import BinanceExchange
from .strategies.base import BaseStrategy
from .strategies.martingale import MartingaleStrategy
from .risk_manager import RiskManager

logger = logging.getLogger(__name__)


def expand_ohlcv_to_seconds(ohlcv_data: List[List], timeframe: str = '1m') -> List[List]:
    """
    将K线数据展开为秒级数据，确保回测精确到秒级别
    
    Args:
        ohlcv_data: 原始K线数据，格式: [[timestamp, open, high, low, close, volume], ...]
        timeframe: 时间周期，如 '1m', '5m', '1h' 等，用于确定每个K线包含多少秒
        
    Returns:
        展开后的秒级数据
    """
    if not ohlcv_data:
        return []
    
    # 解析时间周期（每个K线包含的秒数）
    timeframe_seconds = {
        '1m': 60,
        '5m': 300,
        '15m': 900,
        '30m': 1800,
        '1h': 3600,
        '4h': 14400,
        '1d': 86400,
    }
    
    seconds_per_candle = timeframe_seconds.get(timeframe, 60)
    
    expanded_data = []
    
    for candle in ohlcv_data:
        timestamp = candle[0]
        open_price = candle[1]
        high_price = candle[2]
        low_price = candle[3]
        close_price = candle[4]
        volume = candle[5] if len(candle) > 5 else 0
        
        # 计算价格变化范围
        price_range = high_price - low_price if high_price > low_price else abs(close_price - open_price)
        
        # 将每个K线展开为秒级数据点
        # 使用更真实的插值方法模拟价格在K线内的变化
        for second_offset in range(seconds_per_candle):
            current_timestamp = timestamp + (second_offset * 1000)  # 转换为毫秒
            
            # 计算进度（0到1）
            progress = second_offset / max(seconds_per_candle - 1, 1)  # 避免除零
            
            # 基础价格：从open到close的线性插值
            base_price = open_price + (close_price - open_price) * progress
            
            # 添加波动模拟价格在K线内的变化
            # 使用多个正弦波叠加，模拟更真实的价格波动
            if price_range > 0:
                # 主波动：模拟价格在high和low之间的波动
                main_wave = math.sin(progress * math.pi) * (price_range * 0.5)
                # 次要波动：增加一些随机性
                minor_wave = math.sin(progress * math.pi * 3) * (price_range * 0.1)
                
                current_price = base_price + main_wave * 0.3 + minor_wave * 0.1
            else:
                current_price = base_price
            
            # 确保价格在high和low范围内
            current_price = max(low_price, min(high_price, current_price))
            
            # 创建秒级数据点
            # 为了更真实，high和low稍微偏离当前价格
            price_tolerance = abs(current_price) * 0.0001  # 0.01%的容差
            second_high = min(high_price, current_price + price_tolerance)
            second_low = max(low_price, current_price - price_tolerance)
            
            expanded_candle = [
                current_timestamp,
                round(current_price, 4),  # open
                round(second_high, 4),    # high
                round(second_low, 4),      # low
                round(current_price, 4),   # close
                round(volume / seconds_per_candle, 4)  # 平均分配成交量
            ]
            
            expanded_data.append(expanded_candle)
    
    logger.info(f"K线数据展开: {len(ohlcv_data)} 条 {timeframe} K线 -> {len(expanded_data)} 条秒级数据点")
    return expanded_data


class MockExchange:
    """模拟交易所，用于回测"""
    
    def __init__(self, ohlcv_data: List[List], initial_balance: float = 10000.0):
        """
        初始化模拟交易所
        
        Args:
            ohlcv_data: K线数据，格式: [[timestamp, open, high, low, close, volume], ...]
            initial_balance: 初始余额
        """
        self.ohlcv_data = ohlcv_data
        self.current_index = 0
        self.balance = {
            'total': initial_balance,
            'free': initial_balance,
            'used': 0.0
        }
        self.positions: Dict[str, Dict] = {}  # 持仓信息
        self.orders: List[Dict] = []  # 订单历史
        self.equity_curve: List[Tuple[int, float]] = []  # 权益曲线 [(timestamp, balance)]
        
    def get_current_price(self) -> Optional[float]:
        """获取当前价格"""
        if self.current_index < len(self.ohlcv_data):
            candle = self.ohlcv_data[self.current_index]
            return candle[4]  # close价格
        return None
    
    def get_current_timestamp(self) -> Optional[int]:
        """获取当前时间戳"""
        if self.current_index < len(self.ohlcv_data):
            return self.ohlcv_data[self.current_index][0]
        return None
    
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """获取当前价格（模拟）"""
        price = self.get_current_price()
        if price:
            return {
                'last': price,
                'bid': price * 0.9999,  # 模拟买卖价差
                'ask': price * 1.0001,
                'timestamp': self.get_current_timestamp()
            }
        return None
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1m', limit: int = 100) -> List[List]:
        """获取K线数据（返回当前及之后的数据）"""
        if self.current_index < len(self.ohlcv_data):
            end_index = min(self.current_index + limit, len(self.ohlcv_data))
            return self.ohlcv_data[self.current_index:end_index]
        return []
    
    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """设置杠杆（模拟）"""
        return True
    
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100, since: int = None) -> List[List]:
        """获取K线数据（CCXT兼容接口）"""
        return self.get_ohlcv(symbol, timeframe, limit)
    
    def create_market_order(self, symbol: str, side: str, amount: float, 
                           reduce_only: bool = False) -> Optional[Dict]:
        """
        创建市价订单（模拟）
        
        Args:
            symbol: 交易对
            side: 方向 'buy' 或 'sell'
            amount: 数量（USDT）
            reduce_only: 是否只减仓
            
        Returns:
            订单信息
        """
        price = self.get_current_price()
        if not price:
            return None
        
        # 计算合约数量
        contracts = amount / price
        
        # 检查余额
        if side == 'buy':
            if self.balance['free'] < amount:
                logger.warning(f"余额不足: 需要 {amount} USDT，可用 {self.balance['free']} USDT")
                return None
            self.balance['free'] -= amount
            self.balance['used'] += amount
        else:  # sell
            # 检查持仓
            if symbol not in self.positions or self.positions[symbol].get('contracts', 0) < contracts:
                if reduce_only:
                    logger.warning(f"持仓不足，无法减仓")
                    return None
                # 做空：需要保证金
                margin = amount / 10  # 假设10倍杠杆
                if self.balance['free'] < margin:
                    logger.warning(f"保证金不足")
                    return None
                self.balance['free'] -= margin
                self.balance['used'] += margin
        
        # 更新持仓
        if symbol not in self.positions:
            self.positions[symbol] = {
                'contracts': 0,
                'entry_price': 0,
                'side': 'long' if side == 'buy' else 'short'
            }
        
        pos = self.positions[symbol]
        if side == 'buy':
            # 做多：增加持仓
            if pos['contracts'] == 0:
                pos['entry_price'] = price
                pos['contracts'] = contracts
            else:
                # 加权平均价格
                total_contracts = pos['contracts'] + contracts
                pos['entry_price'] = (pos['entry_price'] * pos['contracts'] + price * contracts) / total_contracts
                pos['contracts'] = total_contracts
        else:
            # 做空或平仓
            if pos['side'] == 'long' and side == 'sell':
                # 平多仓
                if pos['contracts'] >= contracts:
                    pnl = (price - pos['entry_price']) * contracts
                    self.balance['total'] += pnl
                    self.balance['free'] += amount + pnl
                    self.balance['used'] -= amount
                    pos['contracts'] -= contracts
                    if pos['contracts'] == 0:
                        del self.positions[symbol]
                else:
                    logger.warning(f"持仓不足，无法平仓")
                    return None
            elif pos['side'] == 'short' and side == 'sell':
                # 做空：增加空仓
                if pos['contracts'] == 0:
                    pos['entry_price'] = price
                    pos['contracts'] = contracts
                else:
                    total_contracts = pos['contracts'] + contracts
                    pos['entry_price'] = (pos['entry_price'] * pos['contracts'] + price * contracts) / total_contracts
                    pos['contracts'] = total_contracts
        
        # 记录订单
        order = {
            'id': f"mock_{len(self.orders)}",
            'symbol': symbol,
            'side': side,
            'amount': amount,
            'price': price,
            'contracts': contracts,
            'timestamp': self.get_current_timestamp(),
            'status': 'closed',
            'filled': contracts
        }
        self.orders.append(order)
        
        # 更新权益曲线
        self.equity_curve.append((self.get_current_timestamp(), self.balance['total']))
        
        return order
    
    def get_balance(self) -> Dict[str, float]:
        """获取余额"""
        # 更新总余额（包含未实现盈亏）
        total = self.balance['free'] + self.balance['used']
        for symbol, pos in self.positions.items():
            price = self.get_current_price()
            if price and pos['contracts'] > 0:
                if pos['side'] == 'long':
                    pnl = (price - pos['entry_price']) * pos['contracts']
                else:
                    pnl = (pos['entry_price'] - price) * pos['contracts']
                total += pnl
        self.balance['total'] = total
        return self.balance.copy()
    
    def get_positions(self, symbol: str = None) -> List[Dict]:
        """获取持仓"""
        result = []
        for sym, pos in self.positions.items():
            if symbol and sym != symbol:
                continue
            price = self.get_current_price()
            if price:
                if pos['side'] == 'long':
                    unrealized_pnl = (price - pos['entry_price']) * pos['contracts']
                else:
                    unrealized_pnl = (pos['entry_price'] - price) * pos['contracts']
                
                result.append({
                    'symbol': sym,
                    'side': pos['side'],
                    'contracts': pos['contracts'],
                    'entryPrice': pos['entry_price'],
                    'markPrice': price,
                    'unrealizedPnl': unrealized_pnl,
                    'notional': pos['contracts'] * price
                })
        return result
    
    def get_open_position(self, symbol: str = None) -> Optional[Dict]:
        """
        获取当前持仓（如果有）
        
        Args:
            symbol: 交易对符号（可选，如果提供则只获取该交易对的持仓）
            
        Returns:
            持仓信息，如果没有持仓返回None
        """
        positions = self.get_positions(symbol)
        for pos in positions:
            if pos.get('contracts', 0) != 0:
                return pos
        return None
    
    def get_all_open_positions(self) -> Dict[str, Dict]:
        """
        获取所有持仓（字典格式）
        
        Returns:
            字典，key为交易对symbol，value为持仓信息
        """
        positions = self.get_positions()
        result = {}
        for pos in positions:
            contracts = pos.get('contracts', 0)
            if contracts != 0:
                sym = pos.get('symbol')
                if sym:
                    result[sym] = pos
        return result
    
    def close_position(self, symbol: str) -> bool:
        """
        平仓（关闭指定交易对的所有持仓）
        
        Args:
            symbol: 交易对符号
            
        Returns:
            是否成功平仓
        """
        if symbol not in self.positions:
            return False
        
        pos = self.positions[symbol]
        if pos['contracts'] == 0:
            return False
        
        # 获取当前价格
        price = self.get_current_price()
        if not price:
            return False
        
        # 计算盈亏
        contracts = pos['contracts']
        entry_price = pos['entry_price']
        
        if pos['side'] == 'long':
            # 做多平仓：卖出
            pnl = (price - entry_price) * contracts
            # 释放保证金并加上盈亏
            notional = contracts * entry_price
            self.balance['free'] += notional + pnl
            self.balance['used'] -= notional
        else:
            # 做空平仓：买入
            pnl = (entry_price - price) * contracts
            # 释放保证金并加上盈亏
            notional = contracts * entry_price
            margin = notional / 10  # 假设10倍杠杆
            self.balance['free'] += margin + pnl
            self.balance['used'] -= margin
        
        # 更新总余额
        self.balance['total'] = self.balance['free'] + self.balance['used']
        
        # 记录订单
        order = {
            'id': f"mock_close_{len(self.orders)}",
            'symbol': symbol,
            'side': 'sell' if pos['side'] == 'long' else 'buy',
            'amount': contracts * price,
            'price': price,
            'contracts': contracts,
            'timestamp': self.get_current_timestamp(),
            'status': 'closed',
            'filled': contracts,
            'pnl': pnl
        }
        self.orders.append(order)
        
        # 删除持仓
        del self.positions[symbol]
        
        # 更新权益曲线
        self.equity_curve.append((self.get_current_timestamp(), self.balance['total']))
        
        return True
    
    def advance(self):
        """推进到下一个时间点"""
        if self.current_index < len(self.ohlcv_data) - 1:
            self.current_index += 1
            # 更新权益曲线
            balance = self.get_balance()
            self.equity_curve.append((self.get_current_timestamp(), balance['total']))
            return True
        return False


class Backtester:
    """回测引擎"""
    
    def __init__(self, strategy_class, strategy_config: Dict[str, Any], 
                 ohlcv_data: List[List], initial_balance: float = 10000.0,
                 progress_callback: Optional[Callable[[int, int, float, float], None]] = None):
        """
        初始化回测引擎
        
        Args:
            strategy_class: 策略类
            strategy_config: 策略配置
            ohlcv_data: K线数据
            initial_balance: 初始余额
            progress_callback: 进度回调函数，接收 (current, total, percentage, current_balance) 参数
        """
        self.strategy_class = strategy_class
        self.strategy_config = strategy_config
        self.ohlcv_data = ohlcv_data
        self.initial_balance = initial_balance
        self.progress_callback = progress_callback
        
        # 创建模拟交易所
        self.mock_exchange = MockExchange(ohlcv_data, initial_balance)
        
        # 创建风险管理器（简化版）
        # 创建一个临时配置对象
        class TempConfig:
            def __init__(self, config_dict):
                self.stop_loss_percent = config_dict.get('risk', {}).get('stop_loss_percent', 10.0)
                self.take_profit_percent = config_dict.get('risk', {}).get('take_profit_percent', 15.0)
                self.max_loss_percent = config_dict.get('risk', {}).get('max_loss_percent', 20.0)
        
        temp_config = TempConfig(strategy_config)
        risk_manager = RiskManager(self.mock_exchange, temp_config)
        
        # 记录风险管理配置（用于验证止盈逻辑）
        logger.info(
            f"回测风险管理配置: 止损 {temp_config.stop_loss_percent}%, "
            f"止盈 {temp_config.take_profit_percent}%, "
            f"最大亏损 {temp_config.max_loss_percent}%"
        )
        
        # 创建策略实例（使用策略ID 0表示回测）
        self.strategy = strategy_class(
            strategy_id=0,
            exchange=self.mock_exchange,
            risk_manager=risk_manager,
            config=strategy_config
        )
        
        # 回测结果
        self.trades: List[Dict] = []
        self.equity_curve: List[Dict] = []
        
    def run(self) -> Dict[str, Any]:
        """
        运行回测
        
        Returns:
            回测结果字典
        """
        logger.info(f"开始回测，数据点: {len(self.ohlcv_data)}, 初始余额: {self.initial_balance}")
        
        # 初始化策略
        import asyncio
        
        # 检查是否已有运行中的事件循环
        try:
            running_loop = asyncio.get_running_loop()
            # 如果有运行中的循环，抛出错误提示
            raise RuntimeError(
                "Backtester.run() 不能在已有事件循环的上下文中运行。"
                "请确保在同步函数中调用此方法，而不是在 async 函数中。"
            )
        except RuntimeError as e:
            # 如果没有运行中的循环，会抛出 RuntimeError: no running event loop
            # 这是我们期望的情况，继续创建新的循环
            if "no running event loop" not in str(e).lower():
                # 如果是其他错误，重新抛出
                raise
        
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # 启动策略
            loop.run_until_complete(self.strategy.start())
            self.strategy.is_active = True
            self.strategy.is_running = True
            
            # 设置交易回调
            original_notify = self.strategy._notify_trade
            def trade_callback(trade_data):
                original_notify(trade_data)
                self.trades.append(trade_data)
            self.strategy._notify_trade = lambda data: trade_callback(data)
            
            # 执行回测循环
            # 在回测中，每个K线都执行一次策略检查（因为K线数据已经包含了时间信息）
            # 这样可以确保策略能够及时响应价格变化
            total_steps = len(self.ohlcv_data) - 1
            progress_update_interval = max(1, total_steps // 100)  # 每1%更新一次进度
            last_progress_update = 0
            
            logger.info(f"回测循环开始，将处理 {total_steps} 个数据点")
            
            while self.mock_exchange.current_index < total_steps:
                current_index = self.mock_exchange.current_index
                
                # 执行策略检查
                try:
                    should_continue = loop.run_until_complete(self.strategy.run_once())
                    if not should_continue:
                        # 如果策略返回False，检查是否是因为is_active被设置为False
                        # 如果是，我们仍然继续运行（因为策略可能在平仓后需要重新开仓）
                        if not self.strategy.is_active:
                            logger.info("策略已停止，结束回测")
                            break
                except Exception as e:
                    logger.warning(f"策略执行错误: {e}")
                    # 即使出错也继续运行，避免回测中断
                
                # 更新进度（定期更新，避免过于频繁）
                if self.progress_callback and (current_index - last_progress_update >= progress_update_interval or current_index == total_steps - 1):
                    percentage = (current_index + 1) / total_steps * 100
                    current_balance = self.mock_exchange.get_balance()['total']
                    try:
                        self.progress_callback(current_index + 1, total_steps, percentage, current_balance)
                    except Exception as e:
                        logger.warning(f"进度回调失败: {e}")
                    last_progress_update = current_index
                
                # 推进到下一个K线
                if not self.mock_exchange.advance():
                    break
            
            # 停止策略
            loop.run_until_complete(self.strategy.stop())
            
            # 统计平仓原因（用于日志输出）
            take_profit_count = sum(1 for t in self.trades 
                                    if t.get('trade_type') == 'close' 
                                    and t.get('close_reason') == '止盈')
            stop_loss_count = sum(1 for t in self.trades 
                                  if t.get('trade_type') == 'close' 
                                  and t.get('close_reason') == '止损')
            max_loss_count = sum(1 for t in self.trades 
                                 if t.get('trade_type') == 'close' 
                                 and t.get('close_reason') == '最大亏损限制')
            
            # 获取最终持仓状态
            final_position = self.mock_exchange.get_open_position(self.strategy.symbol)
            final_price = self.mock_exchange.get_current_price()
            
            logger.info(
                f"回测完成 - 处理了 {self.mock_exchange.current_index + 1}/{total_steps} 个数据点"
            )
            logger.info(
                f"回测完成 - 平仓统计: 止盈 {take_profit_count}次, "
                f"止损 {stop_loss_count}次, 最大亏损限制 {max_loss_count}次"
            )
            
            if final_position and final_price:
                logger.info(
                    f"回测结束时仍有持仓: {final_position.get('contracts', 0)} 合约, "
                    f"当前价格 {final_price:.4f}, 开仓价格 {final_position.get('entryPrice', 0):.4f}"
                )
            else:
                logger.info("回测结束时无持仓")
            
            # 发送最终进度更新（100%）
            if self.progress_callback:
                final_balance = self.mock_exchange.get_balance()['total']
                try:
                    self.progress_callback(total_steps, total_steps, 100.0, final_balance)
                except Exception as e:
                    logger.warning(f"最终进度回调失败: {e}")
            
        finally:
            loop.close()
        
        # 计算回测结果
        return self._calculate_results()
    
    def _calculate_results(self) -> Dict[str, Any]:
        """计算回测结果"""
        final_balance = self.mock_exchange.get_balance()['total']
        total_return = ((final_balance - self.initial_balance) / self.initial_balance) * 100
        total_return_amount = final_balance - self.initial_balance
        
        # 计算交易统计
        # 安全处理 pnl 值，确保 None 被转换为 0
        def safe_get_pnl(trade):
            pnl = trade.get('pnl')
            return pnl if pnl is not None else 0
        
        win_trades = sum(1 for t in self.trades if safe_get_pnl(t) > 0)
        loss_trades = sum(1 for t in self.trades if safe_get_pnl(t) < 0)
        total_trades = len(self.trades)
        win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0
        
        # 统计平仓原因
        take_profit_closes = sum(1 for t in self.trades 
                                 if t.get('trade_type') == 'close' 
                                 and t.get('close_reason') == '止盈')
        stop_loss_closes = sum(1 for t in self.trades 
                               if t.get('trade_type') == 'close' 
                               and t.get('close_reason') == '止损')
        max_loss_closes = sum(1 for t in self.trades 
                              if t.get('trade_type') == 'close' 
                              and t.get('close_reason') == '最大亏损限制')
        
        # 计算最大回撤
        equity_values = [point[1] for point in self.mock_exchange.equity_curve]
        max_drawdown = 0.0
        max_drawdown_amount = 0.0
        if equity_values:
            peak = equity_values[0]
            for value in equity_values:
                if value is not None and value > peak:
                    peak = value
                if value is not None and peak > 0:
                    drawdown = ((peak - value) / peak) * 100
                    drawdown_amount = peak - value
                    if drawdown > max_drawdown:
                        max_drawdown = drawdown
                        max_drawdown_amount = drawdown_amount
        
        # 计算平均盈亏
        win_pnls = [safe_get_pnl(t) for t in self.trades if safe_get_pnl(t) > 0]
        loss_pnls = [abs(safe_get_pnl(t)) for t in self.trades if safe_get_pnl(t) < 0]
        avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else 0
        avg_loss = sum(loss_pnls) / len(loss_pnls) if loss_pnls else 0
        profit_factor = (sum(win_pnls) / sum(loss_pnls)) if loss_pnls and sum(loss_pnls) > 0 else 0
        
        # 计算夏普比率（简化版）
        sharpe_ratio = 0.0
        if len(equity_values) > 1:
            returns = []
            for i in range(1, len(equity_values)):
                if equity_values[i-1] > 0:
                    ret = (equity_values[i] - equity_values[i-1]) / equity_values[i-1]
                    returns.append(ret)
            if returns:
                import statistics
                mean_return = statistics.mean(returns)
                std_return = statistics.stdev(returns) if len(returns) > 1 else 0
                if std_return > 0:
                    sharpe_ratio = (mean_return / std_return) * (252 ** 0.5)  # 年化
        
        # 计算平均交易收益率
        avg_trade_return = (total_return / total_trades) if total_trades > 0 else 0
        
        # 构建权益曲线数据
        equity_curve_data = [
            {
                'timestamp': point[0],
                'balance': point[1],
                'time': datetime.fromtimestamp(point[0] / 1000).isoformat() if point[0] else None
            }
            for point in self.mock_exchange.equity_curve
        ]
        
        # 构建价格趋势数据（从OHLCV数据中提取，精确到四位小数）
        price_data = []
        for candle in self.ohlcv_data:
            timestamp = candle[0]
            price_data.append({
                'timestamp': timestamp,
                'time': datetime.fromtimestamp(timestamp / 1000).isoformat() if timestamp else None,
                'open': round(candle[1], 4),  # 精确到四位小数
                'high': round(candle[2], 4),
                'low': round(candle[3], 4),
                'close': round(candle[4], 4),
                'volume': round(candle[5], 4) if len(candle) > 5 else 0,
            })
        
        return {
            'initial_balance': self.initial_balance,
            'final_balance': final_balance,
            'total_return': total_return,
            'total_return_amount': total_return_amount,
            'total_trades': total_trades,
            'win_trades': win_trades,
            'loss_trades': loss_trades,
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'max_drawdown_amount': max_drawdown_amount,
            'sharpe_ratio': sharpe_ratio,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_trade_return': avg_trade_return,
            'equity_curve': equity_curve_data,
            'trades': self.trades,
            'price_data': price_data,  # 添加价格数据
            # 平仓原因统计
            'take_profit_closes': take_profit_closes,
            'stop_loss_closes': stop_loss_closes,
            'max_loss_closes': max_loss_closes,
        }

