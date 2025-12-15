"""马丁格尔策略单元测试"""

import pytest
import asyncio
from unittest.mock import Mock, MagicMock, AsyncMock
from datetime import datetime

from ftrader.strategies.martingale import MartingaleStrategy
from ftrader.risk_manager import RiskManager


class TestMartingaleStrategy:
    """测试马丁格尔策略的核心逻辑"""
    
    @pytest.fixture
    def mock_exchange(self):
        """创建模拟交易所"""
        exchange = Mock()
        exchange.testnet = False
        exchange.set_leverage = Mock(return_value=True)
        exchange.get_balance = Mock(return_value={'total': 10000.0, 'free': 10000.0, 'used': 0.0})
        exchange.get_ticker = Mock(return_value={'last': 50000.0})
        exchange.get_open_position = Mock(return_value=None)
        exchange.create_market_order = Mock(return_value={'id': 'test_order_1'})
        exchange.close_position = Mock(return_value=True)
        return exchange
    
    @pytest.fixture
    def mock_risk_manager(self):
        """创建模拟风险管理器"""
        risk_manager = Mock(spec=RiskManager)
        risk_manager.set_initial_balance = Mock()
        risk_manager.set_entry_price = Mock()
        risk_manager.should_close_position = Mock(return_value=(False, None))
        risk_manager.entry_balance = 10000.0
        risk_manager.entry_price = 0.0
        return risk_manager
    
    @pytest.fixture
    def strategy_config(self):
        """创建策略配置"""
        return {
            'trading': {
                'symbol': 'BTC/USDT:USDT',
                'side': 'long',
                'leverage': 10
            },
            'martingale': {
                'initial_position': 200.0,
                'multiplier': 2.0,
                'max_additions': 5
            },
            'trigger': {
                'price_drop_percent': 5.0,  # 5%下跌触发
                'start_immediately': False,
                'addition_cooldown': 60
            },
            'risk': {
                'stop_loss_percent': 10.0,
                'take_profit_percent': 15.0,
                'max_loss_percent': 20.0
            },
            'monitoring': {
                'check_interval': 5
            }
        }
    
    @pytest.fixture
    def strategy(self, mock_exchange, mock_risk_manager, strategy_config):
        """创建策略实例"""
        return MartingaleStrategy(
            strategy_id=1,
            exchange=mock_exchange,
            risk_manager=mock_risk_manager,
            config=strategy_config
        )
    
    def test_calculate_position_size(self, strategy):
        """测试仓位大小计算"""
        # 初始仓位
        assert strategy.calculate_position_size(0) == 200.0
        
        # 第1次加仓：200 * 2^1 = 400
        assert strategy.calculate_position_size(1) == 400.0
        
        # 第2次加仓：200 * 2^2 = 800
        assert strategy.calculate_position_size(2) == 800.0
        
        # 第3次加仓：200 * 2^3 = 1600
        assert strategy.calculate_position_size(3) == 1600.0
    
    def test_check_trigger_condition_long(self, strategy):
        """测试做多时的触发条件检查"""
        strategy.position_side = 'long'
        strategy.price_drop_percent = 5.0
        
        # 参考价格（最高价）
        reference_price = 50000.0
        
        # 价格下跌5%，应该触发
        current_price = 47500.0  # 下跌5%
        assert strategy.check_trigger_condition(current_price, reference_price) == True
        
        # 价格下跌6%，应该触发
        current_price = 47000.0  # 下跌6%
        assert strategy.check_trigger_condition(current_price, reference_price) == True
        
        # 价格下跌4%，不应该触发
        current_price = 48000.0  # 下跌4%
        assert strategy.check_trigger_condition(current_price, reference_price) == False
        
        # 价格没有下跌，不应该触发
        current_price = 50000.0
        assert strategy.check_trigger_condition(current_price, reference_price) == False
        
        # 价格上涨，不应该触发
        current_price = 51000.0
        assert strategy.check_trigger_condition(current_price, reference_price) == False
    
    def test_check_trigger_condition_short(self, strategy):
        """测试做空时的触发条件检查"""
        strategy.position_side = 'short'
        strategy.price_drop_percent = 5.0
        
        # 参考价格（最低价）
        reference_price = 50000.0
        
        # 价格上涨5%，应该触发（做空时反向触发）
        current_price = 52500.0  # 上涨5%
        assert strategy.check_trigger_condition(current_price, reference_price) == True
        
        # 价格上涨6%，应该触发
        current_price = 53000.0  # 上涨6%
        assert strategy.check_trigger_condition(current_price, reference_price) == True
        
        # 价格上涨4%，不应该触发
        current_price = 52000.0  # 上涨4%
        assert strategy.check_trigger_condition(current_price, reference_price) == False
    
    def test_should_add_position_checks(self, strategy):
        """测试加仓条件检查"""
        strategy.max_additions = 5
        strategy.addition_cooldown = 60
        strategy.price_drop_percent = 5.0
        strategy.position_side = 'long'
        
        import time
        current_time = time.time()
        
        # 测试1：达到最大加仓次数，不应该加仓
        strategy.addition_count = 5
        strategy.highest_price = 50000.0
        assert strategy.should_add_position(47500.0) == False
        
        # 测试2：在冷却期内，不应该加仓
        strategy.addition_count = 2
        strategy.last_addition_time = current_time - 30  # 30秒前加仓，冷却期60秒
        strategy.last_addition_price = 48000.0
        strategy.highest_price = 50000.0
        assert strategy.should_add_position(47500.0) == False
        
        # 测试3：价格变化不足，不应该加仓
        strategy.addition_count = 2
        strategy.last_addition_time = current_time - 120  # 120秒前加仓，已过冷却期
        strategy.last_addition_price = 49500.0  # 上次加仓价格
        strategy.highest_price = 50000.0
        # 当前价格49500，从上次加仓价格只下跌了约1%，小于阈值30%（5% * 0.3 = 1.5%）
        assert strategy.should_add_position(49500.0) == False
        
        # 测试4：满足所有条件，应该加仓
        strategy.addition_count = 2
        strategy.last_addition_time = current_time - 120  # 已过冷却期
        strategy.last_addition_price = 49000.0
        strategy.highest_price = 50000.0
        # 当前价格47500，从最高价下跌5%，应该触发
        assert strategy.should_add_position(47500.0) == True
    
    @pytest.mark.asyncio
    async def test_price_drop_triggers_addition(self, strategy, mock_exchange):
        """测试价格下跌触发加仓的完整流程"""
        strategy.is_active = True
        strategy.highest_price = 50000.0  # 初始最高价
        strategy.addition_count = 0
        strategy.last_addition_time = 0
        strategy.last_addition_price = 0
        
        # 模拟有持仓
        mock_exchange.get_open_position.return_value = {
            'contracts': 0.004,  # 200 USDT / 50000
            'side': 'long',
            'entryPrice': 50000.0
        }
        
        # 第一次：价格下跌5%，应该触发加仓
        mock_exchange.get_ticker.return_value = {'last': 47500.0}  # 下跌5%
        
        # 执行一次策略检查
        should_continue = await strategy.run_once()
        
        # 验证：应该调用了开仓（加仓）
        assert should_continue == True
        # 验证加仓大小：第1次加仓 = 200 * 2^1 = 400 USDT
        mock_exchange.create_market_order.assert_called()
        call_args = mock_exchange.create_market_order.call_args
        assert call_args[0][1] == 'buy'  # 做多方向
        assert call_args[0][2] == 400.0  # 加仓大小
        
        # 验证加仓次数已更新
        assert strategy.addition_count == 1
    
    @pytest.mark.asyncio
    async def test_multiple_additions_with_correct_multiplier(self, strategy, mock_exchange):
        """测试多次加仓时倍数是否正确"""
        strategy.is_active = True
        strategy.highest_price = 50000.0
        strategy.last_addition_time = 0
        strategy.last_addition_price = 0
        
        # 模拟有持仓
        mock_exchange.get_open_position.return_value = {
            'contracts': 0.004,
            'side': 'long',
            'entryPrice': 50000.0
        }
        
        import time
        current_time = time.time()
        
        # 第1次加仓：价格下跌5%
        strategy.addition_count = 0
        mock_exchange.get_ticker.return_value = {'last': 47500.0}
        await strategy.run_once()
        assert strategy.addition_count == 1
        # 验证加仓大小：200 * 2^1 = 400
        call_args = mock_exchange.create_market_order.call_args
        assert call_args[0][2] == 400.0
        
        # 第2次加仓：价格继续下跌5%（从47500下跌到45125，约5%）
        strategy.addition_count = 1
        strategy.last_addition_time = current_time - 120  # 已过冷却期
        strategy.last_addition_price = 47500.0
        strategy.highest_price = 47500.0  # 更新参考价格
        mock_exchange.get_ticker.return_value = {'last': 45125.0}  # 从47500下跌约5%
        await strategy.run_once()
        assert strategy.addition_count == 2
        # 验证加仓大小：200 * 2^2 = 800
        call_args = mock_exchange.create_market_order.call_args
        assert call_args[0][2] == 800.0
        
        # 第3次加仓：价格继续下跌5%
        strategy.addition_count = 2
        strategy.last_addition_time = current_time - 120
        strategy.last_addition_price = 45125.0
        strategy.highest_price = 45125.0
        mock_exchange.get_ticker.return_value = {'last': 42868.75}  # 从45125下跌约5%
        await strategy.run_once()
        assert strategy.addition_count == 3
        # 验证加仓大小：200 * 2^3 = 1600
        call_args = mock_exchange.create_market_order.call_args
        assert call_args[0][2] == 1600.0
    
    def test_price_drop_percent_calculation(self, strategy):
        """测试下跌百分比计算"""
        strategy.position_side = 'long'
        strategy.price_drop_percent = 5.0
        
        reference_price = 50000.0
        
        # 测试不同的价格下跌百分比
        test_cases = [
            (47500.0, True, 5.0),   # 下跌5%，应该触发
            (47000.0, True, 6.0),   # 下跌6%，应该触发
            (48000.0, False, 4.0),  # 下跌4%，不应该触发
            (45000.0, True, 10.0),  # 下跌10%，应该触发
            (49000.0, False, 2.0), # 下跌2%，不应该触发
        ]
        
        for current_price, should_trigger, expected_drop in test_cases:
            actual_drop = ((reference_price - current_price) / reference_price) * 100
            triggered = strategy.check_trigger_condition(current_price, reference_price)
            
            assert abs(actual_drop - expected_drop) < 0.1, \
                f"价格 {current_price} 的下跌百分比计算错误，预期 {expected_drop}%，实际 {actual_drop}%"
            assert triggered == should_trigger, \
                f"价格 {current_price} (下跌 {actual_drop:.2f}%) 的触发结果错误，预期 {should_trigger}，实际 {triggered}"
    
    @pytest.mark.asyncio
    async def test_strategy_does_not_add_on_small_drops(self, strategy, mock_exchange):
        """测试小幅下跌不会触发加仓"""
        strategy.is_active = True
        strategy.highest_price = 50000.0
        strategy.addition_count = 0
        strategy.last_addition_time = 0
        strategy.last_addition_price = 0
        
        # 模拟有持仓
        mock_exchange.get_open_position.return_value = {
            'contracts': 0.004,
            'side': 'long',
            'entryPrice': 50000.0
        }
        
        # 价格只下跌2%，不应该触发加仓（阈值是5%）
        mock_exchange.get_ticker.return_value = {'last': 49000.0}  # 下跌2%
        mock_exchange.create_market_order.reset_mock()
        
        await strategy.run_once()
        
        # 验证：不应该调用开仓
        mock_exchange.create_market_order.assert_not_called()
        assert strategy.addition_count == 0
    
    @pytest.mark.asyncio
    async def test_strategy_respects_max_additions(self, strategy, mock_exchange):
        """测试策略遵守最大加仓次数限制"""
        strategy.is_active = True
        strategy.max_additions = 3
        strategy.highest_price = 50000.0
        strategy.addition_count = 3  # 已达到最大加仓次数
        strategy.last_addition_time = 0
        strategy.last_addition_price = 0
        
        # 模拟有持仓
        mock_exchange.get_open_position.return_value = {
            'contracts': 0.014,  # 累计持仓
            'side': 'long',
            'entryPrice': 45000.0
        }
        
        # 价格继续下跌5%，但已达到最大加仓次数
        mock_exchange.get_ticker.return_value = {'last': 42750.0}  # 从45000下跌5%
        mock_exchange.create_market_order.reset_mock()
        
        await strategy.run_once()
        
        # 验证：不应该调用开仓
        mock_exchange.create_market_order.assert_not_called()
        assert strategy.addition_count == 3  # 保持不变


class TestMartingaleStrategyIntegration:
    """集成测试：使用模拟交易所测试完整策略流程"""
    
    def test_complete_martingale_flow(self):
        """测试完整的马丁格尔策略流程"""
        from ftrader.backtester import MockExchange, Backtester
        from ftrader.strategies.martingale import MartingaleStrategy
        
        # 创建模拟K线数据：价格从50000逐步下跌
        ohlcv_data = []
        base_time = int(datetime.now().timestamp() * 1000)
        prices = [50000, 50000, 49000, 48000, 47500, 47000, 46000, 45125, 45000, 44000]
        
        for i, price in enumerate(prices):
            ohlcv_data.append([
                base_time + i * 60000,  # 每分钟一个K线
                price,  # open
                price + 100,  # high
                price - 100,  # low
                price,  # close
                1000.0  # volume
            ])
        
        # 策略配置
        config = {
            'trading': {
                'symbol': 'BTC/USDT:USDT',
                'side': 'long',
                'leverage': 10
            },
            'martingale': {
                'initial_position': 200.0,
                'multiplier': 2.0,
                'max_additions': 3
            },
            'trigger': {
                'price_drop_percent': 5.0,
                'start_immediately': True,  # 立即开仓
                'addition_cooldown': 0  # 无冷却期，方便测试
            },
            'risk': {
                'stop_loss_percent': 50.0,  # 设置很大的止损，避免测试中被触发
                'take_profit_percent': 100.0,
                'max_loss_percent': 100.0
            },
            'monitoring': {
                'check_interval': 1
            }
        }
        
        # 创建回测器
        backtester = Backtester(
            strategy_class=MartingaleStrategy,
            strategy_config=config,
            ohlcv_data=ohlcv_data,
            initial_balance=10000.0
        )
        
        # 运行回测
        results = backtester.run()
        
        # 验证结果
        assert results['total_trades'] > 0, "应该有交易发生"
        
        # 验证初始开仓
        initial_trades = [t for t in results['trades'] if t.get('trade_type') == 'open']
        assert len(initial_trades) > 0, "应该有初始开仓"
        
        # 验证加仓
        addition_trades = [t for t in results['trades'] if t.get('trade_type') == 'add']
        assert len(addition_trades) > 0, "应该有加仓交易"
        
        # 验证加仓金额递增（马丁格尔特性）
        if len(addition_trades) >= 2:
            amounts = [t['amount'] for t in addition_trades]
            # 验证加仓金额是递增的（每次加倍）
            for i in range(1, len(amounts)):
                assert amounts[i] >= amounts[i-1] * 1.5, \
                    f"加仓金额应该递增，第{i}次加仓 {amounts[i]} 应该 >= 第{i-1}次 {amounts[i-1]} * 1.5"
        
        print(f"\n回测结果:")
        print(f"初始余额: {results['initial_balance']}")
        print(f"最终余额: {results['final_balance']}")
        print(f"总收益率: {results['total_return']:.2f}%")
        print(f"总交易次数: {results['total_trades']}")
        print(f"开仓次数: {len(initial_trades)}")
        print(f"加仓次数: {len(addition_trades)}")

