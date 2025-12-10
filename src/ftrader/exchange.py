"""交易所封装模块"""

import ccxt
import time
import logging
from typing import Dict, Optional, List
from decimal import Decimal, ROUND_DOWN

logger = logging.getLogger(__name__)


class BinanceExchange:
    """币安交易所封装类"""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        """
        初始化币安交易所连接
        
        Args:
            api_key: API密钥
            api_secret: API密钥
            testnet: 是否使用测试网
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        # 创建交易所实例
        exchange_class = getattr(ccxt, 'binance')
        
        # 构建配置
        exchange_config = {
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',  # 使用合约市场
            }
        }
        
        # 只有在提供了API密钥时才设置
        if api_key:
            exchange_config['apiKey'] = api_key
        if api_secret:
            exchange_config['secret'] = api_secret
        
        self.exchange = exchange_class(exchange_config)
        
        # 如果是测试网，配置测试网URL
        if testnet:
            self.exchange.enable_demo_trading(True)    
        
        logger.info(f"币安交易所连接初始化完成 (测试网: {testnet})")
    
    def set_leverage(self, symbol: str, leverage: int) -> bool:    
        try:
            # 币安合约设置杠杆需要转换symbol格式
            # BTC/USDT:USDT -> BTCUSDT
            binance_symbol = symbol.replace('/', '').replace(':USDT', 'USDT')
            
            # 使用ccxt的标准方法设置杠杆
            try:
                # 尝试使用set_leverage方法（ccxt标准方法）
                self.exchange.set_leverage(leverage, symbol)
            except AttributeError:
                # 如果不存在，使用币安特定的API
                params = {
                    'symbol': binance_symbol,
                    'leverage': leverage
                }
                self.exchange.fapiPrivate_post_leverage(params)
            
            logger.info(f"设置杠杆倍数: {symbol} = {leverage}x")
            return True
        except Exception as e:
            logger.error(f"设置杠杆失败: {e}")
            return False
    
    def get_balance(self) -> Dict[str, float]:
        """
        获取账户余额
        
        Returns:
            余额字典，包含可用余额和总余额
        """
        try:
            balance = self.exchange.fetch_balance({'type': 'future'})
            return {
                'free': balance.get('USDT', {}).get('free', 0.0),
                'used': balance.get('USDT', {}).get('used', 0.0),
                'total': balance.get('USDT', {}).get('total', 0.0),
            }
        except Exception as e:
            logger.error(f"获取余额失败: {e}")
            return {'free': 0.0, 'used': 0.0, 'total': 0.0}
    
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """
        获取当前价格
        
        Args:
            symbol: 交易对符号
            
        Returns:
            价格信息字典，包含last价格
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return {
                'last': ticker.get('last', 0.0),
                'bid': ticker.get('bid', 0.0),
                'ask': ticker.get('ask', 0.0),
                'timestamp': ticker.get('timestamp', 0),
            }
        except Exception as e:
            logger.error(f"获取价格失败: {e}")
            return None
    
    def get_positions(self, symbol: str) -> List[Dict]:
        """
        获取持仓信息
        
        Args:
            symbol: 交易对符号
            
        Returns:
            持仓列表
        """
        try:
            positions = self.exchange.fetch_positions([symbol])
            return positions
        except Exception as e:
            logger.error(f"获取持仓失败: {e}")
            return []
    
    def get_open_position(self, symbol: str) -> Optional[Dict]:
        """
        获取当前持仓（如果有）
        
        Args:
            symbol: 交易对符号
            
        Returns:
            持仓信息，如果没有持仓返回None
        """
        positions = self.get_positions(symbol)
        for pos in positions:
            if pos.get('contracts', 0) != 0:
                return pos
        return None
    
    def create_market_order(self, symbol: str, side: str, amount: float, 
                           reduce_only: bool = False) -> Optional[Dict]:
        """
        创建市价订单
        
        Args:
            symbol: 交易对符号
            side: 方向 'buy' 或 'sell'
            amount: 数量（USDT）
            reduce_only: 是否只减仓
            
        Returns:
            订单信息
        """
        try:
            # 获取市场信息
            market = self.exchange.market(symbol)
            if not market:
                logger.error(f"无法获取市场信息: {symbol}")
                return None
            
            # 获取当前价格
            ticker = self.get_ticker(symbol)
            if not ticker:
                logger.error("无法获取价格，无法创建订单")
                return None
            
            price = ticker['last']
            contract_size = market.get('contractSize', 1.0)
            
            # 计算合约数量
            # 对于USDT合约，amount就是USDT数量，直接除以价格得到基础货币数量
            # 然后除以合约大小得到合约数量
            base_amount = amount / price
            contracts = base_amount / contract_size
            
            logger.debug(f"订单计算: amount={amount} USDT, price={price}, contract_size={contract_size}, base_amount={base_amount}, contracts={contracts}")
            
            # 使用ccxt的amountToPrecision方法调整精度（推荐方式）
            try:
                contracts = self.exchange.amount_to_precision(symbol, contracts)
                contracts = float(contracts)
                logger.debug(f"使用ccxt精度调整后: contracts={contracts}")
            except Exception as e:
                logger.warning(f"ccxt精度调整失败: {e}，尝试手动调整")
                # 回退到手动精度调整
                amount_precision = market.get('precision', {}).get('amount')
                if amount_precision is not None:
                    try:
                        amount_precision = int(amount_precision)
                        if amount_precision > 0:
                            precision_step = Decimal('0.1') ** amount_precision
                        elif amount_precision == 0:
                            precision_step = Decimal('1')
                        else:
                            precision_step = Decimal('1')
                        
                        contracts_decimal = Decimal(str(contracts)).quantize(
                            precision_step, rounding=ROUND_DOWN
                        )
                        contracts = float(contracts_decimal)
                        logger.debug(f"手动精度调整: amount_precision={amount_precision}, contracts={contracts}")
                    except (ValueError, TypeError) as e2:
                        logger.warning(f"手动精度调整也失败: {e2}")
            
            # 如果精度调整后数量为0，尝试使用更小的精度
            if contracts <= 0:
                logger.warning(f"精度调整后合约数量为0，尝试使用更小精度")
                original_contracts = base_amount / contract_size
                # 尝试使用更小的精度步长（更多小数位）
                for precision in [8, 7, 6, 5, 4, 3, 2, 1]:
                    precision_step = Decimal('0.1') ** precision
                    contracts_decimal = Decimal(str(original_contracts)).quantize(
                        precision_step, rounding=ROUND_DOWN
                    )
                    test_contracts = float(contracts_decimal)
                    if test_contracts > 0:
                        contracts = test_contracts
                        logger.info(f"使用精度{precision}，合约数量: {contracts}")
                        break
            
            if contracts <= 0:
                logger.error(f"计算出的合约数量无效: {contracts}")
                logger.error(f"计算详情: amount={amount} USDT, price={price}, contract_size={contract_size}, base_amount={base_amount}")
                logger.error(f"市场信息: precision={market.get('precision', {})}")
                return None
            
            # 检查订单名义价值（币安要求至少100 USDT）
            notional_value = contracts * price * contract_size
            min_notional = 100.0  # 币安最小订单价值
            
            if notional_value < min_notional and not reduce_only:
                logger.warning(f"订单名义价值 {notional_value:.2f} USDT 小于最小值 {min_notional} USDT")
                logger.warning(f"原始合约数量: {contracts}, 用户配置金额: {amount} USDT")
                
                # 计算需要的最小合约数量（向上取整）
                min_contracts_raw = min_notional / (price * contract_size)
                logger.debug(f"计算最小合约数量: min_notional={min_notional}, price={price}, contract_size={contract_size}, min_contracts_raw={min_contracts_raw}")
                
                # 获取精度信息
                amount_precision = market.get('precision', {}).get('amount', 3)
                if amount_precision is None:
                    amount_precision = 3
                else:
                    amount_precision = int(amount_precision)
                
                logger.debug(f"市场精度信息: amount_precision={amount_precision}")
                
                # 计算精度步长
                if amount_precision > 0:
                    precision_step = Decimal('0.1') ** amount_precision
                else:
                    precision_step = Decimal('1')
                
                logger.debug(f"精度步长: {precision_step}")
                
                # 向上取整到精度步长
                min_contracts_decimal = Decimal(str(min_contracts_raw))
                # 向上取整：如果余数不为0，则加一个精度步长
                remainder = min_contracts_decimal % precision_step
                if remainder > 0:
                    min_contracts_decimal = min_contracts_decimal - remainder + precision_step
                
                min_contracts = float(min_contracts_decimal)
                logger.debug(f"向上取整后合约数量: {min_contracts}")
                
                # 使用ccxt的精度方法格式化（确保符合交易所格式要求）
                try:
                    min_contracts_str = self.exchange.amount_to_precision(symbol, min_contracts)
                    min_contracts_formatted = float(min_contracts_str)
                    logger.debug(f"ccxt格式化后合约数量: {min_contracts_formatted} (原始: {min_contracts})")
                    
                    # 验证格式化后的值是否合理（不应该相差太大）
                    if abs(min_contracts_formatted - min_contracts) > min_contracts * 0.1:  # 相差超过10%认为不合理
                        logger.warning(f"ccxt格式化后的值 {min_contracts_formatted} 与原始值 {min_contracts} 相差太大，使用原始值")
                        min_contracts_formatted = min_contracts
                    
                    # 验证格式化后的名义价值
                    formatted_notional = min_contracts_formatted * price * contract_size
                    if formatted_notional >= min_notional:
                        min_contracts = min_contracts_formatted
                    else:
                        # 如果格式化后不够，使用向上取整的原始值
                        logger.warning(f"ccxt精度格式化后名义价值不足 ({formatted_notional:.2f} USDT)，使用向上取整的原始值")
                except Exception as e:
                    logger.warning(f"ccxt精度格式化失败: {e}，使用手动计算的合约数量")
                
                # 最终验证调整后的名义价值
                final_notional = min_contracts * price * contract_size
                logger.debug(f"最终合约数量: {min_contracts}, 最终名义价值: {final_notional:.2f} USDT")
                
                if final_notional < min_notional:
                    logger.error(f"无法调整到满足最小订单价值: 调整后名义价值 {final_notional:.2f} USDT 仍小于 {min_notional} USDT")
                    logger.error(f"建议增加初始仓位到至少 {min_notional * 1.1:.2f} USDT")
                    return None
                
                # 检查调整后的金额是否超过用户配置金额太多（超过50%则拒绝）
                max_allowed_notional = amount * 1.5  # 允许最多超过50%
                if final_notional > max_allowed_notional:
                    logger.error(f"调整后订单名义价值 {final_notional:.2f} USDT 超过用户配置金额 {amount} USDT 的50%")
                    logger.error(f"为避免意外大额订单，拒绝此次调整")
                    logger.error(f"建议将初始仓位增加到至少 {min_notional * 1.1:.2f} USDT 以满足币安最小订单要求")
                    return None
                
                logger.info(f"调整合约数量从 {contracts} 到 {min_contracts} 以满足最小订单价值要求")
                contracts = min_contracts
                notional_value = contracts * price * contract_size
                logger.info(f"调整后订单名义价值: {notional_value:.2f} USDT (用户配置: {amount} USDT)")
                
                # 检查账户余额是否足够（考虑杠杆）
                try:
                    balance = self.get_balance()
                    available = balance.get('free', 0)
                    # 对于杠杆交易，需要的保证金 = 名义价值 / 杠杆倍数
                    required_margin = notional_value / 10  # 假设10倍杠杆
                    if required_margin > available:
                        logger.error(f"账户余额不足: 需要保证金 {required_margin:.2f} USDT，可用余额 {available:.2f} USDT")
                        logger.error(f"订单名义价值 {notional_value:.2f} USDT 过大，无法执行")
                        return None
                except Exception as e:
                    logger.warning(f"无法检查账户余额: {e}")
            
            # 创建订单参数
            params = {}
            if reduce_only:
                params['reduceOnly'] = True
            
            # 创建订单（使用合约数量）
            order = self.exchange.create_market_order(
                symbol, side, contracts, None, params=params
            )
            
            logger.info(
                f"创建市价订单: {side} {contracts} {symbol} "
                f"(金额: {amount:.2f} USDT, 价格: {price:.2f})"
            )
            return order
            
        except Exception as e:
            logger.error(f"创建订单失败: {e}", exc_info=True)
            return None
    
    def close_position(self, symbol: str) -> bool:
        """
        平仓
        
        Args:
            symbol: 交易对符号
            
        Returns:
            是否成功
        """
        try:
            position = self.get_open_position(symbol)
            if not position:
                logger.info("没有持仓，无需平仓")
                return True
            
            contracts = abs(position.get('contracts', 0))
            if contracts == 0:
                return True
            
            side = 'sell' if position.get('side') == 'long' else 'buy'
            
            # 获取市场信息
            market = self.exchange.market(symbol)
            price = position.get('markPrice', position.get('entryPrice', 0))
            amount = contracts * price * market.get('contractSize', 1)
            
            order = self.create_market_order(symbol, side, amount, reduce_only=True)
            return order is not None
            
        except Exception as e:
            logger.error(f"平仓失败: {e}")
            return False
    
    def get_order_status(self, order_id: str, symbol: str) -> Optional[Dict]:
        """
        查询订单状态
        
        Args:
            order_id: 订单ID
            symbol: 交易对符号
            
        Returns:
            订单信息
        """
        try:
            order = self.exchange.fetch_order(order_id, symbol)
            return order
        except Exception as e:
            logger.error(f"查询订单状态失败: {e}")
            return None
    
    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        取消订单
        
        Args:
            order_id: 订单ID
            symbol: 交易对符号
            
        Returns:
            是否成功
        """
        try:
            self.exchange.cancel_order(order_id, symbol)
            logger.info(f"取消订单: {order_id}")
            return True
        except Exception as e:
            logger.error(f"取消订单失败: {e}")
            return False

