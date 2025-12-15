"""基于大模型LLM和提示词工程的多因子策略模块"""

import logging
import asyncio
import json
import numpy as np
import pandas as pd
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
import aiohttp
import os

from .base import BaseStrategy
from ..exchange import BinanceExchange
from ..risk_manager import RiskManager

logger = logging.getLogger(__name__)


class LLMStrategy(BaseStrategy):
    """基于大模型LLM和提示词工程的多因子策略"""
    
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
        
        # 从配置中提取参数
        trading = config.get('trading', {})
        self.symbol = trading.get('symbol', 'BTC/USDT:USDT')
        self.leverage = trading.get('leverage', 10)
        
        llm_config = config.get('llm', {})
        self.api_provider = llm_config.get('api_provider', 'openai')  # openai, anthropic, custom
        self.api_key = llm_config.get('api_key') or os.getenv('OPENAI_API_KEY') or os.getenv('LLM_API_KEY')
        self.api_base = llm_config.get('api_base')  # 自定义API端点
        self.model = llm_config.get('model', 'gpt-4o-mini')  # 模型名称
        self.temperature = llm_config.get('temperature', 0.3)  # 降低随机性
        self.max_tokens = llm_config.get('max_tokens', 500)
        
        # 提示词配置
        prompt_config = llm_config.get('prompt', {})
        self.system_prompt = prompt_config.get('system_prompt', self._default_system_prompt())
        self.user_prompt_template = prompt_config.get('user_prompt_template', self._default_user_prompt_template())
        self.enable_cot = prompt_config.get('enable_cot', True)  # 启用思维链
        
        # 多因子配置
        factors_config = config.get('factors', {})
        self.lookback_periods = factors_config.get('lookback_periods', 100)  # 历史数据周期
        self.factor_periods = factors_config.get('periods', [5, 10, 20, 50])  # 多周期因子
        self.enable_volume = factors_config.get('enable_volume', True)  # 是否使用成交量
        self.enable_orderbook = factors_config.get('enable_orderbook', False)  # 是否使用订单簿
        
        # 交易参数
        trading_params = config.get('trading_params', {})
        self.position_size = trading_params.get('position_size', 200.0)  # 每次开仓金额
        self.max_position = trading_params.get('max_position', 1)  # 最大持仓数
        self.confidence_threshold = trading_params.get('confidence_threshold', 0.7)  # 置信度阈值
        self.check_interval = config.get('monitoring', {}).get('check_interval', 60)  # 检查间隔（秒）
        
        # 策略状态
        self.current_position: Optional[Dict] = None
        self.price_history: List[float] = []
        self.volume_history: List[float] = []
        self.last_analysis: Optional[Dict] = None
        self.last_llm_call_time: Optional[datetime] = None
        self.llm_call_interval = llm_config.get('call_interval', 300)  # LLM调用间隔（秒）
        
    def get_name(self) -> str:
        """获取策略名称"""
        return "LLM多因子策略"
    
    def get_description(self) -> str:
        """获取策略描述"""
        return f"基于大模型LLM和提示词工程的多因子策略 - {self.symbol}"
    
    def _default_system_prompt(self) -> str:
        """默认系统提示词"""
        return """你是一位专业的加密货币交易分析师。你的任务是分析市场数据并提供交易建议。

请基于提供的市场数据（包括价格、技术指标、成交量等）进行综合分析，然后给出交易建议。

输出格式必须是有效的JSON，包含以下字段：
{
    "analysis": "你的分析过程（如果启用思维链）",
    "signal": "buy" 或 "sell" 或 "hold",
    "confidence": 0.0-1.0之间的浮点数，表示信号的可信度,
    "reasoning": "交易理由的简要说明",
    "risk_level": "low" 或 "medium" 或 "high",
    "price_target": 可选的预期价格目标
}

请确保：
1. 只输出JSON，不要有其他文字
2. confidence必须是一个0-1之间的数字
3. signal必须是 "buy", "sell", 或 "hold" 之一
4. 如果confidence低于0.6，建议使用 "hold"
"""
    
    def _default_user_prompt_template(self) -> str:
        """默认用户提示词模板"""
        return """请分析以下市场数据并给出交易建议：

交易对: {symbol}
当前价格: {current_price}
时间: {timestamp}

=== 价格数据 ===
最近价格: {recent_prices}
价格变化: {price_change}%

=== 技术指标 ===
{indicators_summary}

=== 成交量数据 ===
{volume_summary}

=== 市场趋势 ===
{trend_analysis}

请基于以上信息给出交易建议。"""
    
    def calculate_technical_indicators(self, prices: List[float], period: int = 20) -> Dict[str, float]:
        """
        计算技术指标
        
        Args:
            prices: 价格列表
            period: 计算周期
            
        Returns:
            技术指标字典
        """
        if len(prices) < period:
            return {}
        
        prices_array = np.array(prices[-period:])
        prices_series = pd.Series(prices)
        
        # 简单移动平均线
        sma = np.mean(prices_array)
        
        # 指数移动平均线
        ema = prices_series.ewm(span=period, adjust=False).mean().iloc[-1]
        
        # RSI（相对强弱指标）
        deltas = np.diff(prices_array)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains) if len(gains) > 0 else 0
        avg_loss = np.mean(losses) if len(losses) > 0 else 0
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        # MACD
        if len(prices) >= 26:
            ema12 = prices_series.ewm(span=12, adjust=False).mean().iloc[-1]
            ema26 = prices_series.ewm(span=26, adjust=False).mean().iloc[-1]
            macd = ema12 - ema26
            signal = prices_series.ewm(span=9, adjust=False).mean().iloc[-1]
            macd_hist = macd - signal
        else:
            macd = 0
            macd_hist = 0
        
        # 布林带
        std = np.std(prices_array)
        upper_band = sma + 2 * std
        lower_band = sma - 2 * std
        bb_position = (prices[-1] - lower_band) / (upper_band - lower_band) if (upper_band - lower_band) > 0 else 0.5
        
        # 价格变化率
        price_change = (prices[-1] - prices[-period]) / prices[-period] if prices[-period] > 0 else 0
        
        # 波动率
        volatility = np.std(prices_array) / sma if sma > 0 else 0
        
        # ATR (平均真实波幅)
        if len(prices) >= period + 1:
            high_low = np.abs(np.diff(prices[-period-1:]))
            atr = np.mean(high_low) if len(high_low) > 0 else 0
        else:
            atr = 0
        
        return {
            'sma': sma,
            'ema': ema,
            'rsi': rsi,
            'macd': macd,
            'macd_hist': macd_hist,
            'bb_position': bb_position,
            'price_change': price_change,
            'volatility': volatility,
            'atr': atr,
            'current_price': prices[-1],
            'upper_band': upper_band,
            'lower_band': lower_band
        }
    
    def collect_multi_factor_data(self) -> Dict[str, Any]:
        """
        收集多因子数据
        
        Returns:
            多因子数据字典
        """
        if len(self.price_history) < max(self.factor_periods):
            return {}
        
        factors = {}
        
        # 多周期技术指标
        for period in self.factor_periods:
            indicators = self.calculate_technical_indicators(self.price_history, period)
            if indicators:
                for key, value in indicators.items():
                    factors[f"{key}_{period}"] = value
        
        # 价格趋势
        if len(self.price_history) >= 20:
            recent_prices = self.price_history[-20:]
            factors['price_trend'] = 'up' if recent_prices[-1] > recent_prices[0] else 'down'
            factors['price_momentum'] = (recent_prices[-1] - recent_prices[0]) / recent_prices[0] if recent_prices[0] > 0 else 0
        
        # 成交量分析
        if self.enable_volume and len(self.volume_history) >= 20:
            recent_volume = self.volume_history[-20:]
            factors['volume_avg'] = np.mean(recent_volume)
            factors['volume_trend'] = 'up' if recent_volume[-1] > recent_volume[0] else 'down'
            factors['volume_ratio'] = recent_volume[-1] / np.mean(recent_volume) if np.mean(recent_volume) > 0 else 1
        
        # 价格支撑阻力
        if len(self.price_history) >= 50:
            recent_50 = self.price_history[-50:]
            factors['resistance'] = max(recent_50)
            factors['support'] = min(recent_50)
            factors['price_position'] = (self.price_history[-1] - factors['support']) / (factors['resistance'] - factors['support']) if (factors['resistance'] - factors['support']) > 0 else 0.5
        
        return factors
    
    def format_indicators_summary(self, factors: Dict[str, Any]) -> str:
        """格式化技术指标摘要"""
        summary_parts = []
        
        # 按周期组织
        for period in self.factor_periods:
            period_factors = {k.replace(f"_{period}", ""): v for k, v in factors.items() if k.endswith(f"_{period}")}
            if period_factors:
                summary_parts.append(f"\n周期 {period}:")
                if 'rsi' in period_factors:
                    summary_parts.append(f"  RSI: {period_factors['rsi']:.2f}")
                if 'macd' in period_factors:
                    summary_parts.append(f"  MACD: {period_factors['macd']:.4f}")
                if 'bb_position' in period_factors:
                    summary_parts.append(f"  布林带位置: {period_factors['bb_position']:.2f}")
        
        # 通用指标
        if 'price_trend' in factors:
            summary_parts.append(f"\n价格趋势: {factors['price_trend']}")
        if 'price_momentum' in factors:
            summary_parts.append(f"价格动量: {factors['price_momentum']*100:.2f}%")
        
        return "\n".join(summary_parts) if summary_parts else "无可用指标"
    
    def format_volume_summary(self, factors: Dict[str, Any]) -> str:
        """格式化成交量摘要"""
        if not self.enable_volume:
            return "成交量数据未启用"
        
        summary_parts = []
        if 'volume_avg' in factors:
            summary_parts.append(f"平均成交量: {factors['volume_avg']:.2f}")
        if 'volume_trend' in factors:
            summary_parts.append(f"成交量趋势: {factors['volume_trend']}")
        if 'volume_ratio' in factors:
            summary_parts.append(f"成交量比率: {factors['volume_ratio']:.2f}x")
        
        return "\n".join(summary_parts) if summary_parts else "无成交量数据"
    
    def format_trend_analysis(self, factors: Dict[str, Any]) -> str:
        """格式化趋势分析"""
        analysis_parts = []
        
        if 'resistance' in factors and 'support' in factors:
            current_price = self.price_history[-1] if self.price_history else 0
            analysis_parts.append(f"支撑位: {factors['support']:.2f}")
            analysis_parts.append(f"阻力位: {factors['resistance']:.2f}")
            analysis_parts.append(f"当前价格位置: {factors.get('price_position', 0.5)*100:.1f}%")
        
        return "\n".join(analysis_parts) if analysis_parts else "无趋势数据"
    
    async def call_llm(self, user_prompt: str) -> Optional[Dict[str, Any]]:
        """
        调用LLM API
        
        Args:
            user_prompt: 用户提示词
            
        Returns:
            LLM响应解析后的字典
        """
        if not self.api_key:
            logger.error("LLM API密钥未配置")
            return None
        
        try:
            # 构建API请求
            if self.api_provider == 'openai' or self.api_provider == 'custom':
                api_url = self.api_base or "https://api.openai.com/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "response_format": {"type": "json_object"}  # 强制JSON输出
                }
            else:
                logger.error(f"不支持的API提供商: {self.api_provider}")
                return None
            
            # 发送请求
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"LLM API调用失败: {response.status} - {error_text}")
                        return None
                    
                    result = await response.json()
                    content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                    
                    if not content:
                        logger.error("LLM响应为空")
                        return None
                    
                    # 解析JSON响应
                    try:
                        # 尝试提取JSON（可能包含markdown代码块）
                        if "```json" in content:
                            content = content.split("```json")[1].split("```")[0].strip()
                        elif "```" in content:
                            content = content.split("```")[1].split("```")[0].strip()
                        
                        parsed = json.loads(content)
                        return parsed
                    except json.JSONDecodeError as e:
                        logger.error(f"解析LLM响应JSON失败: {e}, 原始内容: {content[:200]}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error("LLM API调用超时")
            return None
        except Exception as e:
            logger.error(f"调用LLM API失败: {e}", exc_info=True)
            return None
    
    async def analyze_market_with_llm(self) -> Optional[Dict[str, Any]]:
        """
        使用LLM分析市场
        
        Returns:
            分析结果字典
        """
        # 检查调用间隔
        if self.last_llm_call_time:
            time_since_last = (datetime.utcnow() - self.last_llm_call_time).total_seconds()
            if time_since_last < self.llm_call_interval:
                logger.debug(f"距离上次LLM调用时间过短，跳过（还需等待 {int(self.llm_call_interval - time_since_last)} 秒）")
                return self.last_analysis
        
        # 收集多因子数据
        factors = self.collect_multi_factor_data()
        if not factors:
            logger.warning("无法收集足够的因子数据")
            return None
        
        # 构建用户提示词
        current_price = self.price_history[-1] if self.price_history else 0
        recent_prices = self.price_history[-10:] if len(self.price_history) >= 10 else self.price_history
        price_change = ((self.price_history[-1] - self.price_history[-min(20, len(self.price_history))]) / 
                       self.price_history[-min(20, len(self.price_history))] * 100) if len(self.price_history) > 1 else 0
        
        user_prompt = self.user_prompt_template.format(
            symbol=self.symbol,
            current_price=f"{current_price:.2f}",
            timestamp=datetime.utcnow().isoformat(),
            recent_prices=", ".join([f"{p:.2f}" for p in recent_prices[-10:]]),
            price_change=f"{price_change:.2f}",
            indicators_summary=self.format_indicators_summary(factors),
            volume_summary=self.format_volume_summary(factors),
            trend_analysis=self.format_trend_analysis(factors)
        )
        
        logger.info("正在调用LLM分析市场...")
        result = await self.call_llm(user_prompt)
        
        if result:
            self.last_llm_call_time = datetime.utcnow()
            self.last_analysis = result
            logger.info(f"LLM分析完成: signal={result.get('signal')}, confidence={result.get('confidence', 0):.2f}")
            if self.enable_cot and 'analysis' in result:
                logger.debug(f"LLM分析过程: {result['analysis'][:200]}...")
        
        return result
    
    async def get_price_data(self, limit: int = 500) -> tuple[List[float], List[float]]:
        """
        获取历史价格和成交量数据
        
        Args:
            limit: 获取的数据量
            
        Returns:
            (价格列表, 成交量列表)
        """
        loop = asyncio.get_event_loop()
        try:
            ohlcv = await loop.run_in_executor(
                None,
                self.exchange.get_ohlcv,
                self.symbol,
                '1m',
                limit
            )
            if ohlcv:
                prices = [candle[4] for candle in ohlcv]  # close price
                volumes = [candle[5] for candle in ohlcv] if len(ohlcv[0]) > 5 else []
                return prices, volumes
            return [], []
        except Exception as e:
            logger.error(f"获取价格数据失败: {e}")
            return [], []
    
    async def get_current_price(self) -> Optional[float]:
        """获取当前价格（异步）"""
        loop = asyncio.get_event_loop()
        ticker = await loop.run_in_executor(None, self.exchange.get_ticker, self.symbol)
        if ticker:
            return ticker['last']
        return None
    
    async def start(self) -> bool:
        """启动策略（异步）"""
        logger.info("=" * 60)
        logger.info("启动LLM多因子策略")
        logger.info(f"交易对: {self.symbol}")
        logger.info(f"杠杆: {self.leverage}x")
        logger.info(f"LLM模型: {self.model}")
        logger.info(f"API提供商: {self.api_provider}")
        logger.info(f"因子周期: {self.factor_periods}")
        logger.info("=" * 60)
        
        if not self.api_key:
            logger.error("LLM API密钥未配置，策略无法启动")
            return False
        
        # 设置杠杆
        loop = asyncio.get_event_loop()
        leverage_set = await loop.run_in_executor(
            None,
            self.exchange.set_leverage,
            self.symbol,
            self.leverage
        )
        
        if not leverage_set:
            logger.error("设置杠杆失败，策略无法启动")
            return False
        
        # 获取初始余额
        balance = await loop.run_in_executor(None, self.exchange.get_balance)
        if balance is None:
            logger.error("无法获取初始余额，策略启动失败")
            return False
        
        initial_balance = balance['total']
        self.risk_manager.set_initial_balance(initial_balance)
        
        # 加载历史数据
        logger.info("加载历史数据...")
        prices, volumes = await self.get_price_data(self.lookback_periods)
        
        if len(prices) < max(self.factor_periods):
            logger.warning(f"历史数据不足（需要至少 {max(self.factor_periods)} 个样本），策略将在收集足够数据后开始分析")
        
        self.price_history = prices
        self.volume_history = volumes if self.enable_volume else []
        
        self.is_active = True
        logger.info("策略启动成功")
        return True
    
    async def stop(self) -> bool:
        """停止策略（异步）"""
        logger.info("停止策略")
        self.is_active = False
        return True
    
    async def open_position(self, direction: str, price: float) -> bool:
        """
        开仓
        
        Args:
            direction: 方向 ('buy' 或 'sell')
            price: 当前价格
            
        Returns:
            是否成功
        """
        side = 'buy' if direction == 'buy' else 'sell'
        position_side = 'long' if direction == 'buy' else 'short'
        
        try:
            loop = asyncio.get_event_loop()
            order = await loop.run_in_executor(
                None,
                self.exchange.create_market_order,
                self.symbol,
                side,
                self.position_size
            )
            
            if order:
                logger.info(
                    f"开仓成功: {position_side} {self.position_size:.2f} USDT "
                    f"@ {price:.2f} (订单ID: {order.get('id', 'N/A')})"
                )
                
                self.current_position = {
                    'side': position_side,
                    'entry_price': price,
                    'order_id': order.get('id'),
                    'size': self.position_size
                }
                
                # 记录交易
                self.record_trade(
                    trade_type='open',
                    side=position_side,
                    symbol=self.symbol,
                    price=price,
                    amount=self.position_size,
                    order_id=str(order.get('id', ''))
                )
                
                return True
            else:
                logger.error("开仓失败：订单创建失败")
                return False
                
        except Exception as e:
            logger.error(f"开仓失败: {e}")
            return False
    
    async def close_position(self, price: float) -> bool:
        """
        平仓
        
        Args:
            price: 当前价格
            
        Returns:
            是否成功
        """
        try:
            loop = asyncio.get_event_loop()
            closed = await loop.run_in_executor(
                None,
                self.exchange.close_position,
                self.symbol
            )
            
            if closed:
                logger.info("平仓成功")
                
                # 计算盈亏
                balance = await loop.run_in_executor(None, self.exchange.get_balance)
                pnl = None
                
                if balance and self.current_position:
                    entry_balance = self.risk_manager.entry_balance if self.risk_manager.entry_balance > 0 else balance['total']
                    pnl = balance['total'] - entry_balance
                
                # 记录交易
                self.record_trade(
                    trade_type='close',
                    side=self.current_position['side'] if self.current_position else 'long',
                    symbol=self.symbol,
                    price=price,
                    amount=0,
                    pnl=pnl,
                    order_id=''
                )
                
                self.current_position = None
                return True
            else:
                logger.error("平仓失败")
                return False
                
        except Exception as e:
            logger.error(f"平仓失败: {e}")
            return False
    
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
            
            # 更新价格历史
            self.price_history.append(current_price)
            if len(self.price_history) > self.lookback_periods * 2:
                self.price_history = self.price_history[-self.lookback_periods * 2:]
            
            # 如果数据足够，使用LLM分析市场
            if len(self.price_history) >= max(self.factor_periods):
                analysis = await self.analyze_market_with_llm()
                
                if analysis:
                    signal = analysis.get('signal', 'hold')
                    confidence = analysis.get('confidence', 0.0)
                    reasoning = analysis.get('reasoning', '')
                    
                    logger.info(f"LLM分析结果: signal={signal}, confidence={confidence:.2f}, reasoning={reasoning[:50]}...")
                    
                    # 检查是否有持仓
                    loop = asyncio.get_event_loop()
                    position = await loop.run_in_executor(
                        None,
                        self.exchange.get_open_position,
                        self.symbol
                    )
                    
                    has_position = position is not None and abs(position.get('contracts', 0)) > 0
                    
                    if has_position:
                        # 有持仓：检查是否需要平仓
                        position_side = position.get('side', '').lower()
                        
                        should_close = False
                        if position_side == 'long' and signal == 'sell' and confidence >= self.confidence_threshold:
                            should_close = True
                        elif position_side == 'short' and signal == 'buy' and confidence >= self.confidence_threshold:
                            should_close = True
                        
                        # 检查风险管理
                        balance = await loop.run_in_executor(None, self.exchange.get_balance)
                        balance_total = balance['total'] if balance else None
                        risk_should_close, risk_reason = self.risk_manager.should_close_position(
                            current_price, balance_total, position_side
                        )
                        
                        if risk_should_close:
                            logger.warning(f"触发风险管理平仓: {risk_reason}")
                            await self.close_position(current_price)
                        elif should_close:
                            logger.info(f"LLM信号建议平仓: {signal}, 置信度: {confidence:.2f}")
                            await self.close_position(current_price)
                    else:
                        # 无持仓：检查是否应该开仓
                        if signal in ['buy', 'sell'] and confidence >= self.confidence_threshold:
                            logger.info(f"LLM信号建议开仓: {signal}, 置信度: {confidence:.2f}")
                            await self.open_position(signal, current_price)
            
            return True
            
        except Exception as e:
            logger.error(f"策略执行错误: {e}", exc_info=True)
            return True

