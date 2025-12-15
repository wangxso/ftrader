"""网格搜索+随机森林策略模块"""

import logging
import asyncio
import numpy as np
import pandas as pd
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, classification_report

from .base import BaseStrategy
from ..exchange import BinanceExchange
from ..risk_manager import RiskManager

logger = logging.getLogger(__name__)


class RandomForestStrategy(BaseStrategy):
    """网格搜索+随机森林策略"""
    
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
        
        ml_config = config.get('ml', {})
        self.lookback_periods = ml_config.get('lookback_periods', 100)  # 历史数据周期
        self.prediction_horizon = ml_config.get('prediction_horizon', 5)  # 预测未来几个周期
        self.min_samples_to_train = ml_config.get('min_samples_to_train', 200)  # 最少样本数才开始训练
        self.retrain_interval = ml_config.get('retrain_interval', 24 * 60 * 60)  # 重新训练间隔（秒）
        self.confidence_threshold = ml_config.get('confidence_threshold', 0.6)  # 预测置信度阈值
        
        # 网格搜索参数
        grid_search = ml_config.get('grid_search', {})
        self.enable_grid_search = grid_search.get('enable', True)
        self.grid_search_params = grid_search.get('params', {
            'n_estimators': [50, 100, 200],
            'max_depth': [5, 10, 15, None],
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4]
        })
        
        # 交易参数
        trading_params = config.get('trading_params', {})
        self.position_size = trading_params.get('position_size', 200.0)  # 每次开仓金额
        self.max_position = trading_params.get('max_position', 1)  # 最大持仓数
        self.min_hold_time = trading_params.get('min_hold_time', 60)  # 最短持仓时间（秒），避免频繁交易
        self.close_confidence_threshold = trading_params.get('close_confidence_threshold', None)  # 平仓置信度阈值，如果为None则使用confidence_threshold
        self.close_cooldown = trading_params.get('close_cooldown', 30)  # 平仓后冷却时间（秒），避免立即反向开仓
        
        # 如果未设置平仓置信度阈值，使用开仓阈值的1.1倍（更保守）
        if self.close_confidence_threshold is None:
            self.close_confidence_threshold = self.confidence_threshold * 1.1
        
        # 策略状态
        self.model: Optional[RandomForestClassifier] = None
        self.scaler: Optional[StandardScaler] = None
        self.last_retrain_time: Optional[datetime] = None
        self.last_prediction: Optional[Dict] = None
        self.current_position: Optional[Dict] = None
        self.position_open_time: Optional[datetime] = None  # 持仓开仓时间
        self.last_close_time: Optional[datetime] = None  # 上次平仓时间
        self.price_history: List[float] = []
        self.feature_history: List[List[float]] = []
        self.label_history: List[int] = []
        
    def get_name(self) -> str:
        """获取策略名称"""
        return "随机森林策略"
    
    def get_description(self) -> str:
        """获取策略描述"""
        return f"网格搜索+随机森林策略 - {self.symbol}"
    
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
        
        # 简单移动平均线
        sma = np.mean(prices_array)
        
        # 指数移动平均线
        ema = pd.Series(prices).ewm(span=period, adjust=False).mean().iloc[-1]
        
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
            ema12 = pd.Series(prices).ewm(span=12, adjust=False).mean().iloc[-1]
            ema26 = pd.Series(prices).ewm(span=26, adjust=False).mean().iloc[-1]
            macd = ema12 - ema26
            signal = pd.Series(prices).ewm(span=9, adjust=False).mean().iloc[-1]
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
        
        return {
            'sma': sma,
            'ema': ema,
            'rsi': rsi,
            'macd': macd,
            'macd_hist': macd_hist,
            'bb_position': bb_position,
            'price_change': price_change,
            'volatility': volatility,
            'current_price': prices[-1]
        }
    
    def create_features(self, prices: List[float]) -> List[float]:
        """
        创建特征向量
        
        Args:
            prices: 价格列表
            
        Returns:
            特征向量
        """
        if len(prices) < 50:
            return []
        
        features = []
        
        # 计算不同周期的技术指标
        for period in [5, 10, 20, 50]:
            indicators = self.calculate_technical_indicators(prices, period)
            if indicators:
                features.extend([
                    indicators.get('sma', 0),
                    indicators.get('ema', 0),
                    indicators.get('rsi', 50),
                    indicators.get('macd', 0),
                    indicators.get('bb_position', 0.5),
                    indicators.get('price_change', 0),
                    indicators.get('volatility', 0)
                ])
        
        # 添加价格变化特征
        if len(prices) >= 5:
            features.append((prices[-1] - prices[-5]) / prices[-5] if prices[-5] > 0 else 0)
        if len(prices) >= 10:
            features.append((prices[-1] - prices[-10]) / prices[-10] if prices[-10] > 0 else 0)
        if len(prices) >= 20:
            features.append((prices[-1] - prices[-20]) / prices[-20] if prices[-20] > 0 else 0)
        
        return features
    
    def create_labels(self, prices: List[float], horizon: int = 5) -> List[int]:
        """
        创建标签（未来价格走势）
        
        Args:
            prices: 价格列表
            horizon: 预测未来几个周期
            
        Returns:
            标签列表 (1=上涨, 0=下跌)
        """
        labels = []
        for i in range(len(prices) - horizon):
            current_price = prices[i]
            future_price = prices[i + horizon]
            # 1表示上涨，0表示下跌
            label = 1 if future_price > current_price else 0
            labels.append(label)
        return labels
    
    def train_model(self, X: np.ndarray, y: np.ndarray) -> Tuple[RandomForestClassifier, StandardScaler]:
        """
        训练随机森林模型（使用网格搜索优化）
        
        Args:
            X: 特征矩阵
            y: 标签向量
            
        Returns:
            训练好的模型和标准化器
        """
        # 标准化特征
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # 创建基础模型
        base_model = RandomForestClassifier(
            random_state=42,
            n_jobs=-1,
            class_weight='balanced'  # 处理类别不平衡
        )
        
        if self.enable_grid_search and len(X) >= 50:
            # 使用时间序列交叉验证
            tscv = TimeSeriesSplit(n_splits=3)
            
            # 网格搜索
            logger.info("开始网格搜索优化超参数...")
            grid_search = GridSearchCV(
                base_model,
                self.grid_search_params,
                cv=tscv,
                scoring='accuracy',
                n_jobs=-1,
                verbose=0
            )
            
            grid_search.fit(X_scaled, y)
            
            logger.info(f"最佳参数: {grid_search.best_params_}")
            logger.info(f"最佳交叉验证得分: {grid_search.best_score_:.4f}")
            
            model = grid_search.best_estimator_
        else:
            # 使用默认参数
            logger.info("使用默认参数训练模型（样本数不足或网格搜索已禁用）")
            model = base_model
            model.fit(X_scaled, y)
        
        # 评估模型
        y_pred = model.predict(X_scaled)
        accuracy = accuracy_score(y, y_pred)
        logger.info(f"模型训练完成，训练集准确率: {accuracy:.4f}")
        
        return model, scaler
    
    async def get_price_data(self, limit: int = 500) -> List[float]:
        """
        获取历史价格数据
        
        Args:
            limit: 获取的数据量
            
        Returns:
            价格列表
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
                # 提取收盘价
                prices = [candle[4] for candle in ohlcv]  # close price
                return prices
            return []
        except Exception as e:
            logger.error(f"获取价格数据失败: {e}")
            return []
    
    async def start(self) -> bool:
        """启动策略（异步）"""
        logger.info("=" * 60)
        logger.info("启动随机森林策略")
        logger.info(f"交易对: {self.symbol}")
        logger.info(f"杠杆: {self.leverage}x")
        logger.info(f"回看周期: {self.lookback_periods}")
        logger.info(f"预测周期: {self.prediction_horizon}")
        logger.info(f"网格搜索: {'启用' if self.enable_grid_search else '禁用'}")
        logger.info("=" * 60)
        
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
        
        # 加载历史数据并训练初始模型
        logger.info("加载历史数据...")
        prices = await self.get_price_data(self.lookback_periods + self.min_samples_to_train)
        
        if len(prices) < self.min_samples_to_train:
            logger.warning(f"历史数据不足（需要至少 {self.min_samples_to_train} 个样本），策略将在收集足够数据后开始训练")
            self.price_history = prices
        else:
            self.price_history = prices
            # 训练初始模型
            await self._train_initial_model()
        
        self.is_active = True
        self.last_retrain_time = datetime.utcnow()
        
        logger.info("策略启动成功")
        return True
    
    async def _train_initial_model(self):
        """训练初始模型"""
        if len(self.price_history) < self.min_samples_to_train:
            logger.warning(f"价格历史数据不足，无法训练模型（需要 {self.min_samples_to_train}，当前 {len(self.price_history)}）")
            return
        
        logger.info("开始构建训练数据集...")
        logger.info(f"价格历史数据点: {len(self.price_history)}")
        logger.info(f"最小训练样本数: {self.min_samples_to_train}")
        logger.info(f"预测周期: {self.prediction_horizon}")
        
        # 创建特征和标签
        X = []
        y = []
        
        logger.info("正在创建特征和标签...")
        for i in range(self.min_samples_to_train, len(self.price_history) - self.prediction_horizon):
            # 使用历史数据创建特征
            historical_prices = self.price_history[:i+1]
            features = self.create_features(historical_prices)
            
            if features:
                X.append(features)
                # 创建标签
                future_prices = self.price_history[i:i+self.prediction_horizon+1]
                if len(future_prices) > self.prediction_horizon:
                    current_price = future_prices[0]
                    future_price = future_prices[-1]
                    label = 1 if future_price > current_price else 0
                    y.append(label)
        
        if len(X) < 10:
            logger.warning(f"样本数不足，无法训练模型（当前样本数: {len(X)}，需要至少 10 个）")
            return
        
        logger.info(f"数据集构建完成: 特征数 {len(X)}, 标签数 {len(y)}")
        logger.info(f"特征维度: {len(X[0]) if X else 0}")
        logger.info(f"标签分布: 上涨={sum(y)}, 下跌={len(y)-sum(y)}")
        
        X = np.array(X)
        y = np.array(y)
        
        # 训练模型
        try:
            logger.info("开始训练随机森林模型...")
            self.model, self.scaler = self.train_model(X, y)
            logger.info("初始模型训练完成")
        except Exception as e:
            logger.error(f"训练模型失败: {e}", exc_info=True)
            raise
    
    async def stop(self) -> bool:
        """停止策略（异步）"""
        logger.info("停止策略")
        self.is_active = False
        
        # 如果有持仓，可以选择平仓或保持
        # 这里选择保持持仓，让用户手动决定
        
        return True
    
    async def get_current_price(self) -> Optional[float]:
        """获取当前价格（异步）"""
        loop = asyncio.get_event_loop()
        ticker = await loop.run_in_executor(None, self.exchange.get_ticker, self.symbol)
        if ticker:
            return ticker['last']
        return None
    
    async def predict_price_direction(self) -> Optional[Dict[str, Any]]:
        """
        预测价格方向
        
        Returns:
            预测结果字典，包含预测方向、置信度等
        """
        if self.model is None or self.scaler is None:
            return None
        
        if len(self.price_history) < 50:
            return None
        
        # 创建当前特征
        features = self.create_features(self.price_history)
        if not features:
            return None
        
        # 标准化特征
        X = np.array([features])
        X_scaled = self.scaler.transform(X)
        
        # 预测
        prediction = self.model.predict(X_scaled)[0]
        probabilities = self.model.predict_proba(X_scaled)[0]
        confidence = max(probabilities)
        
        return {
            'direction': 'up' if prediction == 1 else 'down',
            'confidence': float(confidence),
            'probabilities': {
                'up': float(probabilities[1]),
                'down': float(probabilities[0])
            }
        }
    
    async def should_open_position(self, prediction: Dict[str, Any]) -> bool:
        """
        判断是否应该开仓
        
        Args:
            prediction: 预测结果
            
        Returns:
            是否应该开仓
        """
        # 检查置信度
        if prediction['confidence'] < self.confidence_threshold:
            return False
        
        # 检查是否已有持仓
        loop = asyncio.get_event_loop()
        position = await loop.run_in_executor(
            None,
            self.exchange.get_open_position,
            self.symbol
        )
        
        if position and abs(position.get('contracts', 0)) > 0:
            return False  # 已有持仓，不开新仓
        
        return True
    
    async def open_position(self, direction: str, price: float) -> bool:
        """
        开仓
        
        Args:
            direction: 方向 ('up' 或 'down')
            price: 当前价格
            
        Returns:
            是否成功
        """
        side = 'buy' if direction == 'up' else 'sell'
        position_side = 'long' if direction == 'up' else 'short'
        
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
                self.position_open_time = datetime.utcnow()  # 记录开仓时间
                
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
                pnl_percent = None
                
                if balance and self.current_position:
                    entry_balance = self.risk_manager.entry_balance if self.risk_manager.entry_balance > 0 else balance['total']
                    pnl = balance['total'] - entry_balance
                    if entry_balance > 0:
                        pnl_percent = (pnl / entry_balance) * 100
                
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
                
                # 重置持仓状态
                self.current_position = None
                self.position_open_time = None
                self.last_close_time = datetime.utcnow()  # 记录平仓时间
                return True
            else:
                logger.error("平仓失败")
                return False
                
        except Exception as e:
            logger.error(f"平仓失败: {e}")
            return False
    
    async def retrain_model_if_needed(self):
        """如果需要，重新训练模型"""
        if self.last_retrain_time is None:
            return
        
        time_since_retrain = (datetime.utcnow() - self.last_retrain_time).total_seconds()
        
        if time_since_retrain >= self.retrain_interval:
            await self.retrain_model(force=False)
    
    async def retrain_model(self, force: bool = False) -> Dict[str, Any]:
        """
        重新训练模型
        
        Args:
            force: 是否强制重新训练（忽略时间间隔）
            
        Returns:
            训练结果字典
        """
        if not force and self.last_retrain_time is not None:
            time_since_retrain = (datetime.utcnow() - self.last_retrain_time).total_seconds()
            if time_since_retrain < self.retrain_interval:
                return {
                    'success': False,
                    'message': f'距离上次训练时间过短，还需等待 {int(self.retrain_interval - time_since_retrain)} 秒'
                }
        
        logger.info("=" * 60)
        logger.info("开始重新训练模型...")
        logger.info(f"策略ID: {self.strategy_id}, 交易对: {self.symbol}")
        if self.last_retrain_time:
            logger.info(f"上次训练时间: {self.last_retrain_time.isoformat()}")
        logger.info("=" * 60)
        
        try:
            # 获取更多历史数据
            logger.info(f"正在获取历史价格数据（需要至少 {self.min_samples_to_train} 个样本）...")
            prices = await self.get_price_data(self.lookback_periods + self.min_samples_to_train)
            logger.info(f"已获取 {len(prices)} 个价格数据点")
            
            if len(prices) < self.min_samples_to_train:
                logger.warning(f"历史数据不足，需要至少 {self.min_samples_to_train} 个样本，当前只有 {len(prices)} 个")
                return {
                    'success': False,
                    'message': f'历史数据不足，需要至少 {self.min_samples_to_train} 个样本，当前只有 {len(prices)} 个'
                }
            
            self.price_history = prices
            logger.info(f"价格历史已更新，共 {len(self.price_history)} 个数据点")
            
            # 训练模型
            logger.info("开始训练模型...")
            await self._train_initial_model()
            
            if self.model is None:
                logger.error("模型训练失败：模型为 None")
                return {
                    'success': False,
                    'message': '模型训练失败'
                }
            
            self.last_retrain_time = datetime.utcnow()
            logger.info(f"训练完成时间: {self.last_retrain_time.isoformat()}")
            
            # 评估模型性能
            accuracy = None
            if hasattr(self.model, 'score'):
                # 如果有足够数据，可以评估
                pass
            
            logger.info("=" * 60)
            logger.info("模型重新训练完成")
            logger.info(f"训练样本数: {len(prices)}")
            logger.info(f"下次训练时间: {(self.last_retrain_time + timedelta(seconds=self.retrain_interval)).isoformat()}")
            logger.info("=" * 60)
            
            return {
                'success': True,
                'message': '模型重新训练成功',
                'last_retrain_time': self.last_retrain_time.isoformat(),
                'training_samples': len(prices)
            }
            
        except Exception as e:
            logger.error(f"重新训练模型失败: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'重新训练失败: {str(e)}'
            }
    
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
            
            # 如果数据足够，训练初始模型
            if self.model is None and len(self.price_history) >= self.min_samples_to_train:
                await self._train_initial_model()
            
            # 检查是否需要重新训练
            await self.retrain_model_if_needed()
            
            # 如果有模型，进行预测
            if self.model is not None:
                prediction = await self.predict_price_direction()
                
                if prediction:
                    self.last_prediction = prediction
                    
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
                        predicted_direction = prediction['direction']
                        
                        # 检查持仓时间（避免刚开仓就平仓）
                        can_close_by_time = True
                        if self.position_open_time:
                            hold_time = (datetime.utcnow() - self.position_open_time).total_seconds()
                            if hold_time < self.min_hold_time:
                                can_close_by_time = False
                                logger.debug(
                                    f"持仓时间过短 ({hold_time:.1f}秒 < {self.min_hold_time}秒)，"
                                    f"暂不平仓，当前预测: {predicted_direction}, 置信度: {prediction['confidence']:.2f}"
                                )
                        
                        should_close = False
                        close_reason = ""
                        
                        # 如果预测方向与持仓方向相反，且置信度超过平仓阈值
                        if position_side == 'long' and predicted_direction == 'down':
                            if prediction['confidence'] > self.close_confidence_threshold and can_close_by_time:
                                should_close = True
                                close_reason = f"预测方向与持仓相反（down），置信度: {prediction['confidence']:.2f}"
                        elif position_side == 'short' and predicted_direction == 'up':
                            if prediction['confidence'] > self.close_confidence_threshold and can_close_by_time:
                                should_close = True
                                close_reason = f"预测方向与持仓相反（up），置信度: {prediction['confidence']:.2f}"
                        
                        # 也检查风险管理（风险管理不受时间限制）
                        balance = await loop.run_in_executor(None, self.exchange.get_balance)
                        balance_total = balance['total'] if balance else None
                        risk_should_close, risk_reason = self.risk_manager.should_close_position(
                            current_price, balance_total, position_side
                        )
                        
                        if risk_should_close:
                            logger.warning(f"触发风险管理平仓: {risk_reason}")
                            await self.close_position(current_price)
                        elif should_close:
                            logger.info(f"平仓: {close_reason}")
                            await self.close_position(current_price)
                    else:
                        # 无持仓：检查是否应该开仓
                        # 检查平仓冷却时间（避免频繁反向开仓）
                        can_open = True
                        if self.last_close_time:
                            time_since_close = (datetime.utcnow() - self.last_close_time).total_seconds()
                            if time_since_close < self.close_cooldown:
                                can_open = False
                                logger.debug(
                                    f"平仓冷却中 ({time_since_close:.1f}秒 < {self.close_cooldown}秒)，"
                                    f"暂不开仓，当前预测: {prediction['direction']}, 置信度: {prediction['confidence']:.2f}"
                                )
                        
                        if can_open and await self.should_open_position(prediction):
                            logger.info(f"预测信号: {prediction['direction']}, 置信度: {prediction['confidence']:.2f}")
                            await self.open_position(prediction['direction'], current_price)
            
            return True
            
        except Exception as e:
            logger.error(f"策略执行错误: {e}", exc_info=True)
            return True

