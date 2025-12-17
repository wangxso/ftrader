"""交易所封装模块"""

import os
import ccxt
import time
import logging
from typing import Dict, Optional, List
from decimal import Decimal, ROUND_DOWN

logger = logging.getLogger(__name__)


class BinanceExchange:
    """币安交易所封装类"""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False, proxy: Optional[str] = None):
        """
        初始化币安交易所连接
        
        Args:
            api_key: API密钥
            api_secret: API密钥
            testnet: 是否使用测试网
            proxy: 代理地址，格式如 'http://127.0.0.1:7890' 或 'socks5://127.0.0.1:1080'
                   如果为 None，则从环境变量 BINANCE_PROXY 读取
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        # 获取代理配置
        if proxy is None:
            import os
            proxy = os.getenv('BINANCE_PROXY', '')
        
        # 创建交易所实例
        exchange_class = getattr(ccxt, 'binance')
        
        # 构建配置
        exchange_config = {
            'enableRateLimit': True,
            'timeout': 20000,  # 20秒超时
            'options': {
                'defaultType': 'future',  # 使用合约市场
            }
        }
        
        # 配置代理
        if proxy:
            # ccxt 使用 'proxies' 参数配置代理
            # 格式: {'http': 'http://proxy:port', 'https': 'http://proxy:port'}
            # 注意：SOCKS5 代理需要安装 requests[socks] 或 PySocks
            exchange_config['proxies'] = {
                'http': proxy,
                'https': proxy,
            }
            logger.info(f"已配置代理: {proxy}")
        
        # 只有在提供了API密钥时才设置
        if api_key:
            exchange_config['apiKey'] = api_key
        if api_secret:
            exchange_config['secret'] = api_secret
        
        # 确保使用future类型
        if testnet:
            exchange_config['options']['defaultType'] = 'future'
        
        self.exchange = exchange_class(exchange_config)
        
        # 如果是测试网，启用Demo Trading模式（币安新的统一测试环境）
        if testnet:
            try:
                # 币安已弃用Futures Sandbox，现在使用新的Demo Trading环境
                # CCXT v4.5.6+ 支持，使用enable_demo_trading方法
                self.exchange.enable_demo_trading(True)
                logger.info("已启用币安Demo Trading模式（新的统一测试环境）")
                # 加载市场信息
                self.exchange.load_markets()
                logger.info("市场信息已加载")
            except Exception as e:
                logger.warning(f"启用Demo Trading模式失败: {e}，将尝试继续")
                # 即使失败也尝试加载市场信息
                try:
                    self.exchange.load_markets()
                except Exception as e2:
                    logger.warning(f"加载市场信息失败: {e2}，将在使用时加载")
        
        logger.info(f"币安交易所连接初始化完成 (测试网: {testnet}, 代理: {'已配置' if proxy else '未配置'})")
    
    def set_leverage(self, symbol: str, leverage: int) -> bool:    
        try:
            # 确保市场信息已加载
            if not hasattr(self.exchange, 'markets') or not self.exchange.markets:
                self.exchange.load_markets()
            
            # 如果symbol是币安格式（如"LUNAUSDT"），需要转换为CCXT格式
            original_symbol = symbol
            
            # 检查是否是币安格式（没有斜杠和冒号）
            if '/' not in symbol and ':' not in symbol:
                # 尝试从markets中找到对应的CCXT格式symbol
                # 币安格式通常是"BASEQUOTE"，需要转换为"BASE/QUOTE:QUOTE"
                found_symbol = None
                for market_id, market_info in self.exchange.markets.items():
                    # 检查market的id是否匹配
                    market_id_value = market_info.get('id')
                    if market_id_value == symbol:
                        found_symbol = market_id
                        break
                    # 尝试匹配币安格式：BASEUSDT -> BASE/USDT:USDT
                    if symbol.endswith('USDT') and market_id.endswith('/USDT:USDT'):
                        base = symbol[:-4]  # 去掉USDT
                        if market_id.startswith(base + '/'):
                            found_symbol = market_id
                            break
                
                if found_symbol:
                    logger.debug(f"将币安格式symbol {symbol} 转换为CCXT格式 {found_symbol}")
                    symbol = found_symbol
                else:
                    logger.warning(f"无法将币安格式symbol {symbol} 转换为CCXT格式，尝试手动构造")
                    # 如果找不到，尝试手动构造CCXT格式
                    if symbol.endswith('USDT'):
                        base = symbol[:-4]
                        symbol = f"{base}/USDT:USDT"
                        logger.info(f"手动构造CCXT格式symbol: {symbol}")
                    elif symbol.endswith('USD'):
                        base = symbol[:-3]
                        symbol = f"{base}/USD:USD"
                        logger.info(f"手动构造CCXT格式symbol: {symbol}")
            
            # 获取市场信息以确定合约类型
            market = self.exchange.market(symbol)
            if not market:
                logger.error(f"无法找到交易对: {symbol} (原始: {original_symbol})")
                return False
            
            # 从市场信息中确定合约类型
            contract_type = None
            # 优先从market的linear/inverse属性获取
            if market.get('linear', False):
                contract_type = 'linear'
            elif market.get('inverse', False):
                contract_type = 'inverse'
            else:
                # 如果market中没有linear/inverse，尝试从其他属性推断
                market_type = market.get('type', '')
                if market_type == 'swap' or market_type == 'future':
                    # 检查market的id或symbol格式
                    market_id = market.get('id', '')
                    if 'USDT' in market_id or '/USDT' in symbol or ':USDT' in symbol:
                        contract_type = 'linear'
                    elif 'USD' in market_id or '/USD' in symbol or ':USD' in symbol:
                        contract_type = 'inverse'
                    else:
                        # 默认使用linear（USDT永续合约）
                        contract_type = 'linear'
                else:
                    # 根据symbol判断
                    if ':USDT' in symbol or '/USDT' in symbol:
                        contract_type = 'linear'
                    elif ':USD' in symbol or '/USD' in symbol:
                        contract_type = 'inverse'
                    else:
                        # 默认使用linear（USDT永续合约）
                        contract_type = 'linear'
            
            # 币安合约设置杠杆需要转换symbol格式
            # BTC/USDT:USDT -> BTCUSDT
            binance_symbol = symbol.replace('/', '').replace(':USDT', 'USDT').replace(':USD', 'USD')
            
            # 使用ccxt的标准方法设置杠杆，需要指定合约类型
            try:
                # CCXT的set_leverage方法签名：set_leverage(leverage, symbol, params={})
                # 对于币安，需要在params中指定type
                logger.info(f"尝试设置杠杆: {symbol} = {leverage}x (类型: {contract_type})")
                params = {'type': contract_type}
                
                # 使用正确的方法名：set_leverage（下划线，不是驼峰）
                self.exchange.set_leverage(leverage, symbol, params)
                
                logger.info(f"设置杠杆成功: {symbol} = {leverage}x (类型: {contract_type})")
                return True
            except Exception as e:
                # 如果标准方法失败，尝试使用币安原生API
                logger.warning(f"使用标准方法设置杠杆失败: {e}，尝试使用币安原生API")
                try:
                    # 使用币安原生API调用
                    if contract_type == 'linear':
                        # USDT永续合约使用fapi/v1/leverage
                        endpoint = 'fapi/v1/leverage'
                    else:
                        # 币本位合约使用dapi/v1/leverage
                        endpoint = 'dapi/v1/leverage'
                    
                    # 构建请求参数
                    request_params = {
                        'symbol': binance_symbol,
                        'leverage': leverage
                    }
                    
                    # 使用private_post方法调用币安API
                    if contract_type == 'linear':
                        response = self.exchange.private_post_fapiv1leverage(request_params)
                    else:
                        response = self.exchange.private_post_dapiv1leverage(request_params)
                    
                    logger.info(f"设置杠杆倍数: {symbol} = {leverage}x (类型: {contract_type})")
                    return True
                except AttributeError:
                    # 如果private_post方法不存在，尝试使用request方法
                    try:
                        if contract_type == 'linear':
                            url = 'fapi/v1/leverage'
                        else:
                            url = 'dapi/v1/leverage'
                        
                        response = self.exchange.request(url, 'POST', {
                            'symbol': binance_symbol,
                            'leverage': leverage
                        })
                        
                        logger.info(f"设置杠杆倍数: {symbol} = {leverage}x (类型: {contract_type})")
                        return True
                    except Exception as e3:
                        logger.error(f"使用request方法设置杠杆也失败: {e3}")
                        # 对于测试网或Demo Trading，可能不需要设置杠杆，记录警告但继续
                        if self.testnet:
                            logger.warning("测试网/Demo Trading模式下设置杠杆失败，但将继续运行（某些测试环境可能不支持设置杠杆）")
                            return True  # 测试网允许继续
                        return False
                except Exception as e2:
                    logger.error(f"使用币安原生API设置杠杆失败: {e2}")
                    # 对于测试网或Demo Trading，可能不需要设置杠杆
                    if self.testnet:
                        logger.warning("测试网/Demo Trading模式下设置杠杆失败，但将继续运行（某些测试环境可能不支持设置杠杆）")
                        return True  # 测试网允许继续
                    return False
            
        except Exception as e:
            logger.error(f"设置杠杆失败: {e}", exc_info=True)
            # 对于测试网，允许继续运行
            if self.testnet:
                logger.warning("测试网模式下设置杠杆失败，但将继续运行")
                return True
            return False
    
    def get_balance(self) -> Optional[Dict[str, float]]:
        """
        获取账户余额
        
        Returns:
            余额字典，包含可用余额和总余额，如果获取失败返回None
        """
        try:
            balance = self.exchange.fetch_balance({'type': 'future'})
            logger.debug(f"获取余额: {balance}")
            result = {
                'free': balance.get('USDT', {}).get('free', 0.0),
                'used': balance.get('USDT', {}).get('used', 0.0),
                'total': balance.get('USDT', {}).get('total', 0.0),
            }
            # 如果余额为0，可能是网络错误，记录警告
            if result['total'] == 0.0:
                logger.warning("获取的余额为0，可能是网络错误或账户确实为0")
            return result
        except Exception as e:
            logger.error(f"获取余额失败: {e}")
            # 返回None而不是默认值0，避免误判
            return None
    
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
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1m', limit: int = 100) -> List[List]:
        """
        获取K线数据（OHLCV）
        
        Args:
            symbol: 交易对符号
            timeframe: 时间周期，如 '1m', '5m', '1h', '1d'
            limit: 返回的K线数量
            
        Returns:
            K线数据列表，格式: [[timestamp, open, high, low, close, volume], ...]
        """
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            logger.error(f"获取K线数据失败: {e}")
            return []
    
    def get_positions(self, symbol: str = None) -> List[Dict]:
        """
        获取所有持仓信息
        
        Args:
            symbol: 交易对符号（可选，如果提供则只获取该交易对的持仓）
            
        Returns:
            持仓列表
        """
        try:
            if symbol:
                positions = self.exchange.fetch_positions([symbol])
            else:
                positions = self.exchange.fetch_positions()
            return positions
        except Exception as e:
            logger.error(f"获取持仓失败: {e}")
            return []
    
    def get_open_position(self, symbol: str = None) -> Optional[Dict]:
        """
        获取当前持仓（如果有）
        
        Args:
            symbol: 交易对符号（可选，如果不提供则返回所有持仓中的第一个）
            
        Returns:
            持仓信息，如果没有持仓返回None。如果symbol为None，返回第一个有持仓的交易对
        """
        positions = self.get_positions(symbol)
        for pos in positions:
            if pos.get('contracts', 0) != 0:
                return pos
        return None
    
    def get_all_open_positions(self) -> Dict[str, Dict]:
        """
        获取所有持仓（按交易对分组）
        
        Returns:
            字典，key为交易对symbol，value为持仓信息
        """
        positions = self.get_positions()
        result = {}
        for pos in positions:
            contracts = pos.get('contracts', 0)
            if contracts != 0:
                symbol = pos.get('symbol')
                if symbol:
                    result[symbol] = pos
        return result
    
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
            # 确保markets已加载
            if not self.exchange.markets or len(self.exchange.markets) == 0:
                logger.info("市场信息未加载，正在加载...")
                self.exchange.load_markets()
            
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
            # 获取合约大小，确保不是None
            contract_size = market.get('contractSize')
            if contract_size is None or contract_size <= 0:
                # 对于USDT永续合约，contractSize通常是1，表示1个合约 = 1个基础货币单位
                # 如果market中没有contractSize或值为None/无效，默认使用1.0
                contract_size = 1.0
                logger.debug(f"合约大小未设置或无效，使用默认值1.0")
            
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
            
            # 检查最小数量精度（在检查名义价值之前）
            limits = market.get('limits', {})
            amount_limits = limits.get('amount', {})
            min_amount = amount_limits.get('min')
            
            # 如果市场信息中没有最小数量，从precision中获取
            if min_amount is None or min_amount <= 0:
                precision = market.get('precision', {})
                amount_precision = precision.get('amount')
                if amount_precision:
                    if isinstance(amount_precision, str):
                        min_amount = float(amount_precision)
                    else:
                        # 如果是数字，表示小数位数，计算最小步长
                        min_amount = 10 ** (-int(amount_precision))
                else:
                    # 默认最小精度为 0.001
                    min_amount = 0.001
            
            if contracts < min_amount:
                logger.error(
                    f"订单数量 {contracts} 小于最小精度 {min_amount}。"
                    f"原始金额: {amount} USDT, 价格: {price}, 合约大小: {contract_size}, "
                    f"计算出的合约数量: {contracts}"
                )
                logger.error(
                    f"建议增加订单金额到至少 {min_amount * price * contract_size * 1.1:.2f} USDT "
                    f"以满足最小精度要求"
                )
                return None
            
            # 检查订单名义价值
            notional_value = contracts * price * contract_size
            
            # 从市场信息中获取最小订单价值
            limits = market.get('limits', {})
            cost_limits = limits.get('cost', {})
            min_notional = cost_limits.get('min')
            
            # 如果市场信息中没有，使用默认值（根据合约类型不同而不同）
            if min_notional is None or min_notional <= 0:
                # 对于USDT永续合约，默认通常是5 USDT，但币安期货通常是100 USDT
                # 可以根据market的linear/inverse属性判断
                if market.get('linear', False):
                    min_notional = 5.0  # USDT永续合约通常更小
                else:
                    min_notional = 100.0  # 币本位合约通常更大
                logger.debug(f"市场信息中未找到最小订单价值，使用默认值: {min_notional} USDT (合约类型: {'linear' if market.get('linear', False) else 'inverse'})")
            else:
                logger.debug(f"从市场信息获取最小订单价值: {min_notional} USDT")
            
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
                
                # 检查调整后的金额是否超过用户配置金额太多
                # 如果是为了满足最小订单要求，允许调整；否则限制在50%以内
                max_allowed_notional = max(amount * 1.5, min_notional)  # 允许调整到最小订单要求，或最多超过50%
                if final_notional > max_allowed_notional and final_notional > min_notional * 1.1:
                    # 只有当调整后的金额明显超过最小订单要求时，才检查是否超过用户配置的50%
                    if final_notional > amount * 1.5:
                        logger.error(f"调整后订单名义价值 {final_notional:.2f} USDT 超过用户配置金额 {amount} USDT 的50%")
                        logger.error(f"为避免意外大额订单，拒绝此次调整")
                        logger.error(f"建议将初始仓位增加到至少 {min_notional * 1.1:.2f} USDT 以满足最小订单要求")
                        return None
                
                logger.info(f"调整合约数量从 {contracts} 到 {min_contracts} 以满足最小订单价值要求")
                contracts = min_contracts
                notional_value = contracts * price * contract_size
                logger.info(f"调整后订单名义价值: {notional_value:.2f} USDT (用户配置: {amount} USDT)")
                
                # 检查账户余额是否足够（考虑杠杆）
                try:
                    balance = self.get_balance()
                    available = balance.get('free', 0)
                    
                    # 获取杠杆倍数：优先从持仓信息中获取，如果没有持仓则从市场信息中获取
                    leverage = 1  # 默认杠杆倍数
                    try:
                        # 尝试从持仓信息中获取杠杆倍数
                        position = self.get_open_position(symbol)
                        if position:
                            leverage = position.get('leverage', leverage)
                        else:
                            # 如果没有持仓，尝试从市场信息中获取
                            # 币安市场信息中可能包含默认杠杆
                            leverage = market.get('leverage', leverage)
                    except Exception as e:
                        logger.debug(f"无法获取杠杆倍数: {e}，使用默认值 {leverage}")
                    
                    # 对于杠杆交易，需要的保证金 = 名义价值 / 杠杆倍数
                    required_margin = notional_value / leverage
                    logger.debug(f"订单计算: 名义价值={notional_value:.2f} USDT, 杠杆={leverage}x, 需要保证金={required_margin:.2f} USDT")
                    
                    if required_margin > available:
                        logger.error(f"账户余额不足: 需要保证金 {required_margin:.2f} USDT，可用余额 {available:.2f} USDT")
                        logger.error(f"订单名义价值 {notional_value:.2f} USDT (杠杆 {leverage}x) 过大，无法执行")
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
            logger.info(f"取消订单: {order_id} {symbol}")
            self.exchange.cancel_order(order_id, symbol)
            return True
        except Exception as e:
            logger.error(f"取消订单失败: {e}")
            return False
    
    def create_limit_order(self, symbol: str, side: str, amount: float, price: float,
                          reduce_only: bool = False) -> Optional[Dict]:
        """
        创建限价订单
        
        Args:
            symbol: 交易对符号
            side: 方向 'buy' 或 'sell'
            amount: 数量（USDT）
            price: 限价价格
            reduce_only: 是否只减仓
            
        Returns:
            订单信息
        """
        try:
            # 确保markets已加载
            logger.info(f"创建限价订单: {symbol} {side} {amount} {price} {reduce_only}")
            if not self.exchange.markets or len(self.exchange.markets) == 0:
                logger.info("市场信息未加载，正在加载...")
                self.exchange.load_markets()
            
            # 获取市场信息
            market = self.exchange.market(symbol)
            if not market:
                logger.error(f"无法获取市场信息: {symbol}")
                return None
            
            # 获取合约大小，确保不是None
            contract_size = market.get('contractSize')
            if contract_size is None or contract_size <= 0:
                contract_size = 1.0
                logger.debug(f"合约大小未设置或无效，使用默认值1.0")
            
            # 计算合约数量
            base_amount = amount / price
            contracts = base_amount / contract_size
            
            # 使用ccxt的精度调整
            try:
                contracts = self.exchange.amount_to_precision(symbol, contracts)
                contracts = float(contracts)
                price = float(self.exchange.price_to_precision(symbol, price))
            except Exception as e:
                logger.warning(f"精度调整失败: {e}")
                return None
            
            if contracts <= 0:
                logger.error(f"计算出的合约数量无效: {contracts}")
                return None
            
            # 检查订单名义价值
            notional_value = contracts * price * contract_size
            
            # 从市场信息中获取最小订单价值
            limits = market.get('limits', {})
            cost_limits = limits.get('cost', {})
            min_notional = cost_limits.get('min')
            
            # 如果市场信息中没有，使用默认值（根据合约类型不同而不同）
            if min_notional is None or min_notional <= 0:
                if market.get('linear', False):
                    min_notional = 5.0  # USDT永续合约通常更小
                else:
                    min_notional = 100.0  # 币本位合约通常更大
                logger.debug(f"市场信息中未找到最小订单价值，使用默认值: {min_notional} USDT")
            else:
                logger.debug(f"从市场信息获取最小订单价值: {min_notional} USDT")
            
            if notional_value < min_notional and not reduce_only:
                logger.warning(f"订单名义价值 {notional_value:.2f} USDT 小于最小值 {min_notional} USDT")
                return None
            
            # 创建订单参数
            params = {}
            if reduce_only:
                params['reduceOnly'] = True
            
            # 创建限价订单
            order = self.exchange.create_limit_order(
                symbol, side, contracts, price, params=params
            )
            
            logger.info(
                f"创建限价订单: {side} {contracts} {symbol} @ {price} "
                f"(金额: {amount:.2f} USDT)"
            )
            return order
            
        except Exception as e:
            logger.error(f"创建限价订单失败: {e}", exc_info=True)
            return None

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    # 优先使用测试网API密钥
    use_testnet = os.getenv('BINANCE_TESTNET', 'False').lower() == 'true'
    if use_testnet:
        api_key = os.getenv('BINANCE_TESTNET_API_KEY') or os.getenv('BINANCE_API_KEY', '')
        api_secret = os.getenv('BINANCE_TESTNET_SECRET_KEY') or os.getenv('BINANCE_SECRET_KEY', '')
    else:
        api_key = os.getenv('BINANCE_API_KEY', '')
        api_secret = os.getenv('BINANCE_SECRET_KEY', '')
    
    if not api_key or not api_secret:
        raise ValueError("API密钥未设置。请设置 BINANCE_TESTNET_API_KEY 和 BINANCE_TESTNET_SECRET_KEY（测试网）或 BINANCE_API_KEY 和 BINANCE_SECRET_KEY（实盘）")
    
    exchange = BinanceExchange(api_key=api_key, api_secret=api_secret, testnet=use_testnet)
    balance = exchange.get_balance()
    print(balance)

    