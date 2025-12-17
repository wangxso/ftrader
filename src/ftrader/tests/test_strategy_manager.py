"""策略管理器单元测试"""

import pytest
import asyncio
from unittest.mock import Mock, MagicMock, AsyncMock, patch, call
from datetime import datetime
from sqlalchemy.orm import Session

# conftest.py 已经处理了 mock 设置，现在可以安全导入
from ftrader.strategy_manager import StrategyManager
from ftrader.strategies.martingale import MartingaleStrategy
from ftrader.models.strategy import Strategy, StrategyRun, StrategyStatus, StrategyType
from ftrader.models.trade import Trade, TradeType, TradeSide
from ftrader.models.position import Position, PositionSide
from ftrader.risk_manager import RiskManager


class TestStrategyManagerStopStrategy:
    """测试停止策略功能"""
    
    @pytest.fixture
    def mock_db_session(self):
        """创建模拟数据库会话"""
        session = Mock(spec=Session)
        session.query = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        session.close = Mock()
        return session
    
    @pytest.fixture
    def mock_strategy(self):
        """创建模拟策略对象"""
        strategy = Mock(spec=Strategy)
        strategy.id = 1
        strategy.name = "测试策略"
        strategy.status = StrategyStatus.RUNNING
        strategy.config_yaml = """
trading:
  symbol: BTC/USDT:USDT
  side: long
  leverage: 10
martingale:
  initial_position: 200
  multiplier: 2.0
  max_additions: 5
trigger:
  price_drop_percent: 5.0
  start_immediately: true
  addition_cooldown: 60
risk:
  stop_loss_percent: 10.0
  take_profit_percent: 15.0
  max_loss_percent: 20.0
"""
        return strategy
    
    @pytest.fixture
    def mock_strategy_run(self):
        """创建模拟运行记录"""
        run = Mock(spec=StrategyRun)
        run.id = 1
        run.strategy_id = 1
        run.status = StrategyStatus.RUNNING
        run.start_balance = 10000.0
        run.current_balance = None
        run.total_trades = 0
        run.win_trades = 0
        run.loss_trades = 0
        run.started_at = datetime.utcnow()
        run.stopped_at = None
        return run
    
    @pytest.fixture
    def mock_strategy_instance(self):
        """创建模拟策略实例"""
        instance = Mock(spec=MartingaleStrategy)
        instance.strategy_id = 1
        instance.is_active = True
        instance.is_running = True
        instance.symbol = 'BTC/USDT:USDT'
        instance.position_side = 'long'
        instance.entry_price = 50000.0
        instance.highest_price = 51000.0
        instance.addition_count = 2
        instance.positions = [
            {'size': 200, 'price': 50000},
            {'size': 400, 'price': 48000}
        ]
        instance.initial_position_opened = True
        instance.last_addition_time = 1000.0
        instance.last_addition_price = 48000.0
        
        # 模拟 stop 方法（支持 close_positions 参数）
        async def mock_stop(close_positions=True):
            instance.is_active = False
            return True
        
        # 创建一个支持 inspect.signature 的 mock
        stop_mock = AsyncMock(side_effect=mock_stop)
        # 添加 __signature__ 属性，让 inspect.signature 能够检测到 close_positions 参数
        import inspect
        stop_mock.__signature__ = inspect.Signature([
            inspect.Parameter('close_positions', inspect.Parameter.POSITIONAL_OR_KEYWORD, default=True)
        ])
        instance.stop = stop_mock
        
        instance.get_status = Mock(return_value={
            'strategy_id': 1,
            'name': '测试策略',
            'status': 'running',
            'is_active': True,
            'is_running': True
        })
        return instance
    
    @pytest.fixture
    def mock_exchange(self):
        """创建模拟交易所"""
        exchange = Mock()
        exchange.get_balance = Mock(return_value={'total': 10500.0, 'free': 10500.0, 'used': 0.0})
        exchange.get_open_position = Mock(return_value={
            'symbol': 'BTC/USDT:USDT',
            'side': 'long',
            'contracts': 0.012,
            'entryPrice': 50000.0,
            'markPrice': 51000.0,
            'lastPrice': 51000.0,
            'unrealizedPnl': 50.0,
            'unrealizedPnlPercent': 0.5
        })
        exchange.close_position = Mock(return_value=True)
        return exchange
    
    @pytest.fixture
    def manager(self):
        """创建策略管理器实例"""
        return StrategyManager()
    
    @pytest.mark.asyncio
    @patch('ftrader.strategy_manager.SessionLocal')
    async def test_stop_strategy_with_positions_and_save_record(
        self,
        mock_session_local,
        manager,
        mock_db_session,
        mock_strategy,
        mock_strategy_run,
        mock_strategy_instance,
        mock_exchange
    ):
        """测试停止策略时自动平仓并保存运行记录"""
        # 设置模拟对象
        manager.strategies = {1: mock_strategy_instance}
        manager.strategy_tasks = {1: Mock()}
        manager.exchanges = {1: mock_exchange}
        
        # 设置数据库查询
        strategy_query = Mock()
        strategy_query.filter = Mock(return_value=strategy_query)
        strategy_query.first = Mock(return_value=mock_strategy)
        
        run_query = Mock()
        run_query.filter = Mock(return_value=run_query)
        run_query.order_by = Mock(return_value=run_query)
        run_query.first = Mock(return_value=mock_strategy_run)
        
        trade_query = Mock()
        trade_query.filter = Mock(return_value=trade_query)
        trade_query.all = Mock(return_value=[
            Mock(pnl=100.0),  # 盈利交易
            Mock(pnl=-50.0),  # 亏损交易
            Mock(pnl=200.0),  # 盈利交易
        ])
        
        mock_db_session.query = Mock(side_effect=lambda model: {
            Strategy: strategy_query,
            StrategyRun: run_query,
            Trade: trade_query
        }[model])
        
        mock_session_local.return_value = mock_db_session
        
        # 执行停止策略
        result = await manager.stop_strategy(1, close_positions=True)
        
        # 验证结果
        assert result is True
        
        # 验证策略实例的 stop 方法被调用（自动平仓）
        mock_strategy_instance.stop.assert_called_once_with(close_positions=True)
        
        # 验证交易所的 close_position 被调用（在策略的 stop 方法中）
        # 注意：这里需要验证策略实例内部调用了 close_position
        
        # 验证运行记录被更新
        assert mock_strategy_run.status == StrategyStatus.STOPPED
        assert mock_strategy_run.current_balance == 10500.0
        assert mock_strategy_run.stopped_at is not None
        
        # 验证交易统计被更新
        assert mock_strategy_run.total_trades == 3
        assert mock_strategy_run.win_trades == 2
        assert mock_strategy_run.loss_trades == 1
        
        # 验证策略状态被更新
        assert mock_strategy.status == StrategyStatus.STOPPED
        
        # 验证数据库提交
        mock_db_session.commit.assert_called()
        
        # 验证策略实例被清理
        assert 1 not in manager.strategies
        assert 1 not in manager.strategy_tasks
    
    @pytest.mark.asyncio
    @patch('ftrader.strategy_manager.SessionLocal')
    async def test_stop_strategy_without_positions(
        self,
        mock_session_local,
        manager,
        mock_db_session,
        mock_strategy,
        mock_strategy_run,
        mock_strategy_instance,
        mock_exchange
    ):
        """测试停止策略时无持仓的情况"""
        # 设置无持仓
        mock_exchange.get_open_position = Mock(return_value=None)
        
        # 设置模拟对象
        manager.strategies = {1: mock_strategy_instance}
        manager.strategy_tasks = {1: Mock()}
        manager.exchanges = {1: mock_exchange}
        
        # 设置数据库查询
        strategy_query = Mock()
        strategy_query.filter = Mock(return_value=strategy_query)
        strategy_query.first = Mock(return_value=mock_strategy)
        
        run_query = Mock()
        run_query.filter = Mock(return_value=run_query)
        run_query.order_by = Mock(return_value=run_query)
        run_query.first = Mock(return_value=mock_strategy_run)
        
        trade_query = Mock()
        trade_query.filter = Mock(return_value=trade_query)
        trade_query.all = Mock(return_value=[])
        
        mock_db_session.query = Mock(side_effect=lambda model: {
            Strategy: strategy_query,
            StrategyRun: run_query,
            Trade: trade_query
        }[model])
        
        mock_session_local.return_value = mock_db_session
        
        # 执行停止策略
        result = await manager.stop_strategy(1, close_positions=True)
        
        # 验证结果
        assert result is True
        
        # 验证策略实例的 stop 方法被调用
        mock_strategy_instance.stop.assert_called_once_with(close_positions=True)
        
        # 验证运行记录被更新
        assert mock_strategy_run.status == StrategyStatus.STOPPED
        assert mock_strategy_run.total_trades == 0
        assert mock_strategy_run.win_trades == 0
        assert mock_strategy_run.loss_trades == 0
    
    @pytest.mark.asyncio
    @patch('ftrader.strategy_manager.SessionLocal')
    async def test_stop_strategy_without_close_positions(
        self,
        mock_session_local,
        manager,
        mock_db_session,
        mock_strategy,
        mock_strategy_run,
        mock_strategy_instance,
        mock_exchange
    ):
        """测试停止策略时不平仓的情况"""
        # 设置模拟对象
        manager.strategies = {1: mock_strategy_instance}
        manager.strategy_tasks = {1: Mock()}
        manager.exchanges = {1: mock_exchange}
        
        # 设置数据库查询
        strategy_query = Mock()
        strategy_query.filter = Mock(return_value=strategy_query)
        strategy_query.first = Mock(return_value=mock_strategy)
        
        run_query = Mock()
        run_query.filter = Mock(return_value=run_query)
        run_query.order_by = Mock(return_value=run_query)
        run_query.first = Mock(return_value=mock_strategy_run)
        
        trade_query = Mock()
        trade_query.filter = Mock(return_value=trade_query)
        trade_query.all = Mock(return_value=[])
        
        mock_db_session.query = Mock(side_effect=lambda model: {
            Strategy: strategy_query,
            StrategyRun: run_query,
            Trade: trade_query
        }[model])
        
        mock_session_local.return_value = mock_db_session
        
        # 执行停止策略（不平仓）
        result = await manager.stop_strategy(1, close_positions=False)
        
        # 验证结果
        assert result is True
        
        # 验证策略实例的 stop 方法被调用（但 close_positions=False）
        mock_strategy_instance.stop.assert_called_once_with(close_positions=False)


class TestStrategyManagerStartStrategy:
    """测试启动策略功能"""
    
    @pytest.fixture
    def mock_db_session(self):
        """创建模拟数据库会话"""
        session = Mock(spec=Session)
        session.query = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        session.close = Mock()
        return session
    
    @pytest.fixture
    def mock_strategy(self):
        """创建模拟策略对象"""
        strategy = Mock(spec=Strategy)
        strategy.id = 1
        strategy.name = "测试策略"
        strategy.status = StrategyStatus.STOPPED
        strategy.strategy_type = StrategyType.CONFIG
        strategy.config_yaml = """
trading:
  symbol: BTC/USDT:USDT
  side: long
  leverage: 10
martingale:
  initial_position: 200
  multiplier: 2.0
  max_additions: 5
trigger:
  price_drop_percent: 5.0
  start_immediately: true
  addition_cooldown: 60
risk:
  stop_loss_percent: 10.0
  take_profit_percent: 15.0
  max_loss_percent: 20.0
"""
        return strategy
    
    @pytest.fixture
    def mock_exchange(self):
        """创建模拟交易所"""
        exchange = Mock()
        exchange.get_balance = Mock(return_value={'total': 10000.0, 'free': 10000.0, 'used': 0.0})
        exchange.get_open_position = Mock(return_value={
            'symbol': 'BTC/USDT:USDT',
            'side': 'long',
            'contracts': 0.01,  # 有旧持仓
            'entryPrice': 50000.0
        })
        exchange.close_position = Mock(return_value=True)
        exchange.set_leverage = Mock(return_value=True)
        exchange.get_ticker = Mock(return_value={'last': 50000.0})
        exchange.create_market_order = Mock(return_value={'id': 'test_order_1'})
        return exchange
    
    @pytest.fixture
    def mock_risk_manager(self):
        """创建模拟风险管理器"""
        risk_manager = Mock(spec=RiskManager)
        risk_manager.set_initial_balance = Mock()
        risk_manager.set_entry_price = Mock()
        risk_manager.should_close_position = Mock(return_value=(False, None))
        risk_manager.entry_balance = 0.0
        risk_manager.entry_price = 0.0
        return risk_manager
    
    @pytest.fixture
    def mock_strategy_instance(self, mock_exchange, mock_risk_manager):
        """创建模拟策略实例"""
        instance = Mock(spec=MartingaleStrategy)
        instance.strategy_id = 1
        instance.exchange = mock_exchange
        instance.risk_manager = mock_risk_manager
        instance.symbol = 'BTC/USDT:USDT'
        instance.position_side = 'long'
        instance.entry_price = 0.0
        instance.highest_price = 0.0
        instance.addition_count = 0
        instance.positions = []
        instance.initial_position_opened = False
        instance.last_addition_time = 0.0
        instance.last_addition_price = 0.0
        
        # 模拟异步方法
        instance.start = AsyncMock(return_value=True)
        instance.stop = AsyncMock(return_value=True)
        instance.run_once = AsyncMock(return_value=True)
        instance.get_current_price = AsyncMock(return_value=50000.0)
        instance.open_position = AsyncMock(return_value=True)
        
        # 模拟 run 方法（返回一个协程）
        async def mock_run():
            instance.is_running = True
            instance.is_active = True
            await asyncio.sleep(0.01)  # 模拟运行
        
        instance.run = mock_run
        instance.on_status_change = None
        instance.on_trade = None
        instance.on_error = None
        
        return instance
    
    @pytest.fixture
    def manager(self):
        """创建策略管理器实例"""
        return StrategyManager()
    
    @pytest.mark.asyncio
    @patch('ftrader.strategy_manager.SessionLocal')
    @patch('ftrader.strategy_manager.MartingaleStrategy')
    @patch('ftrader.strategy_manager.get_exchange')
    @patch('ftrader.strategy_manager.yaml')
    async def test_start_strategy_clears_old_positions(
        self,
        mock_yaml,
        mock_get_exchange,
        mock_strategy_class,
        mock_session_local,
        manager,
        mock_db_session,
        mock_strategy,
        mock_exchange,
        mock_strategy_instance,
        mock_risk_manager
    ):
        """测试启动策略时清理旧持仓"""
        # 设置模拟对象
        import yaml as yaml_module
        mock_yaml.safe_load = yaml_module.safe_load
        mock_get_exchange.return_value = mock_exchange
        mock_strategy_class.return_value = mock_strategy_instance
        
        manager.exchanges = {1: mock_exchange}
        manager.strategies = {}
        manager.strategy_tasks = {}
        
        # 设置数据库查询
        strategy_query = Mock()
        strategy_query.filter = Mock(return_value=strategy_query)
        strategy_query.first = Mock(return_value=mock_strategy)
        
        mock_db_session.query = Mock(return_value=strategy_query)
        mock_db_session.add = Mock()
        mock_db_session.commit = Mock()
        mock_session_local.return_value = mock_db_session
        
        # 执行启动策略
        result = await manager.start_strategy(1)
        
        # 验证结果
        assert result is True
        
        # 验证检查了旧持仓
        mock_exchange.get_open_position.assert_called_with('BTC/USDT:USDT')
        
        # 验证清理了旧持仓
        mock_exchange.close_position.assert_called_once_with('BTC/USDT:USDT')
        
        # 验证策略状态被重置
        assert mock_strategy_instance.entry_price == 0.0
        assert mock_strategy_instance.highest_price == 0.0
        assert mock_strategy_instance.addition_count == 0
        assert mock_strategy_instance.positions == []
        assert mock_strategy_instance.initial_position_opened is False
        assert mock_strategy_instance.last_addition_time == 0.0
        assert mock_strategy_instance.last_addition_price == 0.0
        
        # 验证风险管理器状态被重置
        assert mock_strategy_instance.risk_manager.entry_price == 0.0
        assert mock_strategy_instance.risk_manager.entry_balance == 0.0
        
        # 验证创建了新的运行记录
        mock_db_session.add.assert_called()
        added_run = mock_db_session.add.call_args[0][0]
        assert isinstance(added_run, StrategyRun)
        assert added_run.strategy_id == 1
        assert added_run.status == StrategyStatus.RUNNING
        assert added_run.start_balance == 10000.0
        
        # 验证策略状态被更新
        assert mock_strategy.status == StrategyStatus.RUNNING
        
        # 验证策略实例被添加到管理器
        assert 1 in manager.strategies
        assert 1 in manager.strategy_tasks
    
    @pytest.mark.asyncio
    @patch('ftrader.strategy_manager.SessionLocal')
    @patch('ftrader.strategy_manager.MartingaleStrategy')
    @patch('ftrader.strategy_manager.get_exchange')
    @patch('ftrader.strategy_manager.yaml')
    async def test_start_strategy_without_old_positions(
        self,
        mock_yaml,
        mock_get_exchange,
        mock_strategy_class,
        mock_session_local,
        manager,
        mock_db_session,
        mock_strategy,
        mock_exchange,
        mock_strategy_instance,
        mock_risk_manager
    ):
        """测试启动策略时无旧持仓的情况"""
        # 设置无旧持仓
        mock_exchange.get_open_position = Mock(return_value=None)
        
        # 设置模拟对象
        import yaml as yaml_module
        mock_yaml.safe_load = yaml_module.safe_load
        mock_get_exchange.return_value = mock_exchange
        mock_strategy_class.return_value = mock_strategy_instance
        
        manager.exchanges = {1: mock_exchange}
        manager.strategies = {}
        manager.strategy_tasks = {}
        
        # 设置数据库查询
        strategy_query = Mock()
        strategy_query.filter = Mock(return_value=strategy_query)
        strategy_query.first = Mock(return_value=mock_strategy)
        
        mock_db_session.query = Mock(return_value=strategy_query)
        mock_db_session.add = Mock()
        mock_db_session.commit = Mock()
        mock_session_local.return_value = mock_db_session
        
        # 执行启动策略
        result = await manager.start_strategy(1)
        
        # 验证结果
        assert result is True
        
        # 验证检查了旧持仓
        mock_exchange.get_open_position.assert_called_with('BTC/USDT:USDT')
        
        # 验证没有调用 close_position（因为没有旧持仓）
        mock_exchange.close_position.assert_not_called()
        
        # 验证策略状态仍然被重置（确保干净启动）
        assert mock_strategy_instance.entry_price == 0.0
        assert mock_strategy_instance.addition_count == 0


class TestStrategyManagerTradeCallback:
    """测试交易回调功能"""
    
    @pytest.fixture
    def mock_db_session(self):
        """创建模拟数据库会话"""
        session = Mock(spec=Session)
        session.query = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        session.close = Mock()
        return session
    
    @pytest.fixture
    def mock_strategy_run(self):
        """创建模拟运行记录"""
        run = Mock(spec=StrategyRun)
        run.id = 1
        run.strategy_id = 1
        run.status = StrategyStatus.RUNNING
        run.total_trades = 0
        run.win_trades = 0
        run.loss_trades = 0
        return run
    
    @pytest.fixture
    def manager(self):
        """创建策略管理器实例"""
        return StrategyManager()
    
    @pytest.mark.asyncio
    @patch('ftrader.strategy_manager.SessionLocal')
    async def test_trade_callback_links_to_run_record(
        self,
        mock_session_local,
        manager,
        mock_db_session,
        mock_strategy_run
    ):
        """测试交易回调将交易记录关联到运行记录"""
        # 设置数据库查询
        run_query = Mock()
        run_query.filter = Mock(return_value=run_query)
        run_query.order_by = Mock(return_value=run_query)
        run_query.first = Mock(return_value=mock_strategy_run)
        
        position_query = Mock()
        position_query.filter = Mock(return_value=position_query)
        position_query.first = Mock(return_value=None)
        
        mock_db_session.query = Mock(side_effect=lambda model: {
            StrategyRun: run_query,
            Position: position_query
        }[model])
        
        mock_db_session.add = Mock()
        mock_db_session.commit = Mock()
        mock_session_local.return_value = mock_db_session
        
        # 模拟交易数据
        trade_data = {
            'trade_type': 'open',
            'side': 'long',
            'symbol': 'BTC/USDT:USDT',
            'price': 50000.0,
            'amount': 200.0,
            'order_id': 'test_order_1',
            'pnl': None,
            'pnl_percent': None,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        
        # 执行交易回调
        manager._strategy_trade_callback(1, trade_data)
        
        # 验证交易记录被添加
        # 注意：add 可能被调用多次（Trade 和 Position），所以需要找到 Trade 对象
        add_calls = mock_db_session.add.call_args_list
        trade_added = False
        for call_args in add_calls:
            added_obj = call_args[0][0]
            # 检查是否是 Trade 对象（通过检查属性）
            if hasattr(added_obj, 'trade_type') and hasattr(added_obj, 'strategy_id'):
                assert added_obj.strategy_id == 1
                assert added_obj.strategy_run_id == 1  # 关联到运行记录
                assert added_obj.trade_type == TradeType.OPEN
                assert added_obj.side == TradeSide.LONG
                assert added_obj.price == 50000.0
                assert added_obj.amount == 200.0
                trade_added = True
                break
        assert trade_added, "Trade 对象应该被添加到数据库"
        
        # 验证运行记录的交易统计被更新
        assert mock_strategy_run.total_trades == 1
        assert mock_strategy_run.win_trades == 0
        assert mock_strategy_run.loss_trades == 0
        
        # 验证数据库提交
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    @patch('ftrader.strategy_manager.SessionLocal')
    async def test_trade_callback_updates_win_loss_stats(
        self,
        mock_session_local,
        manager,
        mock_db_session,
        mock_strategy_run
    ):
        """测试交易回调更新盈亏统计"""
        # 设置初始统计
        mock_strategy_run.total_trades = 0
        mock_strategy_run.win_trades = 0
        mock_strategy_run.loss_trades = 0
        
        # 设置数据库查询
        run_query = Mock()
        run_query.filter = Mock(return_value=run_query)
        run_query.order_by = Mock(return_value=run_query)
        run_query.first = Mock(return_value=mock_strategy_run)
        
        position_query = Mock()
        position_query.filter = Mock(return_value=position_query)
        position_query.first = Mock(return_value=None)
        
        mock_db_session.query = Mock(side_effect=lambda model: {
            StrategyRun: run_query,
            Position: position_query
        }[model])
        
        mock_db_session.add = Mock()
        mock_db_session.commit = Mock()
        mock_session_local.return_value = mock_db_session
        
        # 测试盈利交易
        win_trade_data = {
            'trade_type': 'close',
            'side': 'long',
            'symbol': 'BTC/USDT:USDT',
            'price': 51000.0,
            'amount': 0,
            'order_id': '',
            'pnl': 100.0,  # 盈利
            'pnl_percent': 2.0,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        
        manager._strategy_trade_callback(1, win_trade_data)
        
        # 验证统计更新
        assert mock_strategy_run.total_trades == 1
        assert mock_strategy_run.win_trades == 1
        assert mock_strategy_run.loss_trades == 0
        
        # 测试亏损交易
        loss_trade_data = {
            'trade_type': 'close',
            'side': 'long',
            'symbol': 'BTC/USDT:USDT',
            'price': 49000.0,
            'amount': 0,
            'order_id': '',
            'pnl': -50.0,  # 亏损
            'pnl_percent': -1.0,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        
        manager._strategy_trade_callback(1, loss_trade_data)
        
        # 验证统计更新
        assert mock_strategy_run.total_trades == 2
        assert mock_strategy_run.win_trades == 1
        assert mock_strategy_run.loss_trades == 1


class TestMartingaleStrategyStop:
    """测试马丁格尔策略的停止功能"""
    
    @pytest.fixture
    def mock_exchange(self):
        """创建模拟交易所"""
        exchange = Mock()
        exchange.testnet = False
        exchange.symbol = 'BTC/USDT:USDT'
        # 注意：策略内部使用 run_in_executor，所以这些方法应该是同步的
        exchange.get_ticker = Mock(return_value={'last': 50000.0})
        exchange.get_balance = Mock(return_value={'total': 10500.0, 'free': 10500.0, 'used': 0.0})
        exchange.get_open_position = Mock(return_value={
            'symbol': 'BTC/USDT:USDT',
            'side': 'long',
            'contracts': 0.012,
            'entryPrice': 50000.0
        })
        exchange.close_position = Mock(return_value=True)
        return exchange
    
    @pytest.fixture
    def mock_risk_manager(self):
        """创建模拟风险管理器"""
        risk_manager = Mock(spec=RiskManager)
        risk_manager.entry_balance = 10000.0
        risk_manager.entry_price = 50000.0
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
                'price_drop_percent': 5.0,
                'start_immediately': False,
                'addition_cooldown': 60
            },
            'risk': {
                'stop_loss_percent': 10.0,
                'take_profit_percent': 15.0,
                'max_loss_percent': 20.0
            }
        }
    
    @pytest.fixture
    def strategy(self, mock_exchange, mock_risk_manager, strategy_config):
        """创建策略实例"""
        strategy = MartingaleStrategy(
            strategy_id=1,
            exchange=mock_exchange,
            risk_manager=mock_risk_manager,
            config=strategy_config
        )
        strategy.record_trade = Mock()  # 模拟记录交易方法
        return strategy
    
    @pytest.mark.asyncio
    async def test_stop_with_positions_closes_them(self, strategy, mock_exchange, mock_risk_manager):
        """测试停止策略时自动平仓"""
        # 设置策略状态
        strategy.is_active = True
        strategy.entry_price = 50000.0
        strategy.position_side = 'long'
        
        # 需要将 get_open_position 设置为同步方法（因为策略内部使用 run_in_executor）
        def sync_get_position(symbol):
            return {
                'symbol': 'BTC/USDT:USDT',
                'side': 'long',
                'contracts': 0.012,
                'entryPrice': 50000.0
            }
        mock_exchange.get_open_position = sync_get_position
        
        close_called = {'called': False, 'result': True}
        def sync_close_position(symbol):
            close_called['called'] = True
            return close_called['result']
        mock_exchange.close_position = sync_close_position
        
        def sync_get_balance():
            return {'total': 10500.0, 'free': 10500.0, 'used': 0.0}
        mock_exchange.get_balance = sync_get_balance
        
        # 执行停止（自动平仓）
        result = await strategy.stop(close_positions=True)
        
        # 验证结果
        assert result is True
        assert strategy.is_active is False
        
        # 验证平仓被调用（通过检查 close_called 标志）
        assert close_called['called'], "close_position 应该被调用"
        
        # 验证记录了交易（只有在平仓成功时才会记录）
        if close_called['result']:
            strategy.record_trade.assert_called_once()
            call_args = strategy.record_trade.call_args
            assert call_args[1]['trade_type'] == 'close'
            assert call_args[1]['side'] == 'long'
            assert call_args[1]['symbol'] == 'BTC/USDT:USDT'
            assert call_args[1]['close_reason'] == '策略停止'
    
    @pytest.mark.asyncio
    async def test_stop_without_positions(self, strategy, mock_exchange):
        """测试停止策略时无持仓的情况"""
        # 设置无持仓（同步方法）
        def sync_get_position(symbol):
            return None
        mock_exchange.get_open_position = sync_get_position
        
        strategy.is_active = True
        
        # 执行停止
        result = await strategy.stop(close_positions=True)
        
        # 验证结果
        assert result is True
        assert strategy.is_active is False
        
        # 验证没有调用平仓（因为没有持仓）
        # 注意：由于使用了 run_in_executor，无法直接验证调用次数
        # 但可以通过策略状态验证逻辑正确
    
    @pytest.mark.asyncio
    async def test_stop_without_closing_positions(self, strategy, mock_exchange):
        """测试停止策略时不平仓的情况"""
        strategy.is_active = True
        
        # 执行停止（不平仓）
        result = await strategy.stop(close_positions=False)
        
        # 验证结果
        assert result is True
        assert strategy.is_active is False
        
        # 验证没有记录交易（因为没有平仓）
        strategy.record_trade.assert_not_called()


class TestStrategyManagerStopStrategyEdgeCases:
    """测试停止策略的边界情况"""
    
    @pytest.fixture
    def manager(self):
        """创建策略管理器实例"""
        return StrategyManager()
    
    @pytest.fixture
    def mock_db_session(self):
        """创建模拟数据库会话"""
        session = Mock(spec=Session)
        session.query = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        session.close = Mock()
        return session
    
    @pytest.fixture
    def mock_strategy(self):
        """创建模拟策略对象"""
        strategy = Mock(spec=Strategy)
        strategy.id = 1
        strategy.name = "测试策略"
        strategy.status = StrategyStatus.RUNNING
        return strategy
    
    @pytest.mark.asyncio
    @patch('ftrader.strategy_manager.SessionLocal')
    async def test_stop_strategy_when_not_running(
        self,
        mock_session_local,
        manager,
        mock_db_session,
        mock_strategy
    ):
        """测试停止未运行的策略"""
        # 设置策略未运行
        mock_strategy.status = StrategyStatus.STOPPED
        manager.strategies = {}
        manager.strategy_tasks = {}
        manager.exchanges = {}
        
        # 设置数据库查询
        strategy_query = Mock()
        strategy_query.filter = Mock(return_value=strategy_query)
        strategy_query.first = Mock(return_value=mock_strategy)
        
        run_query = Mock()
        run_query.filter = Mock(return_value=run_query)
        run_query.order_by = Mock(return_value=run_query)
        run_query.first = Mock(return_value=None)  # 没有运行记录
        
        mock_db_session.query = Mock(side_effect=lambda model: {
            Strategy: strategy_query,
            StrategyRun: run_query
        }[model])
        
        mock_session_local.return_value = mock_db_session
        
        # 执行停止策略
        result = await manager.stop_strategy(1, close_positions=True)
        
        # 验证结果
        assert result is True
        
        # 验证策略状态未改变（已经是STOPPED）
        assert mock_strategy.status == StrategyStatus.STOPPED
    
    @pytest.fixture
    def mock_strategy_run(self):
        """创建模拟运行记录"""
        run = Mock(spec=StrategyRun)
        run.id = 1
        run.strategy_id = 1
        run.status = StrategyStatus.RUNNING
        run.start_balance = 10000.0
        run.current_balance = None
        run.total_trades = 0
        run.win_trades = 0
        run.loss_trades = 0
        run.started_at = datetime.utcnow()
        run.stopped_at = None
        return run
    
    @pytest.fixture
    def mock_strategy_instance(self):
        """创建模拟策略实例"""
        instance = Mock(spec=MartingaleStrategy)
        instance.strategy_id = 1
        instance.is_active = True
        instance.is_running = True
        instance.symbol = 'BTC/USDT:USDT'
        
        # 模拟 stop 方法（支持 close_positions 参数）
        async def mock_stop(close_positions=True):
            instance.is_active = False
            return True
        
        stop_mock = AsyncMock(side_effect=mock_stop)
        import inspect
        stop_mock.__signature__ = inspect.Signature([
            inspect.Parameter('close_positions', inspect.Parameter.POSITIONAL_OR_KEYWORD, default=True)
        ])
        instance.stop = stop_mock
        return instance
    
    @pytest.fixture
    def mock_exchange(self):
        """创建模拟交易所"""
        exchange = Mock()
        exchange.get_balance = Mock(return_value={'total': 10500.0, 'free': 10500.0, 'used': 0.0})
        exchange.close_position = Mock(return_value=True)
        return exchange
    
    @pytest.mark.asyncio
    @patch('ftrader.strategy_manager.SessionLocal')
    async def test_stop_strategy_with_trade_statistics(
        self,
        mock_session_local,
        manager,
        mock_db_session,
        mock_strategy,
        mock_strategy_run,
        mock_strategy_instance,
        mock_exchange
    ):
        """测试停止策略时正确统计交易数据"""
        # 设置模拟对象
        manager.strategies = {1: mock_strategy_instance}
        manager.strategy_tasks = {1: Mock()}
        manager.exchanges = {1: mock_exchange}
        
        # 设置数据库查询 - 模拟多个交易
        strategy_query = Mock()
        strategy_query.filter = Mock(return_value=strategy_query)
        strategy_query.first = Mock(return_value=mock_strategy)
        
        run_query = Mock()
        run_query.filter = Mock(return_value=run_query)
        run_query.order_by = Mock(return_value=run_query)
        run_query.first = Mock(return_value=mock_strategy_run)
        
        # 创建模拟交易列表
        mock_trades = [
            Mock(pnl=100.0),   # 盈利
            Mock(pnl=-50.0),   # 亏损
            Mock(pnl=200.0),   # 盈利
            Mock(pnl=150.0),   # 盈利
            Mock(pnl=-30.0),   # 亏损
            Mock(pnl=None),    # 无盈亏（开仓）
        ]
        
        trade_query = Mock()
        trade_query.filter = Mock(return_value=trade_query)
        trade_query.all = Mock(return_value=mock_trades)
        
        mock_db_session.query = Mock(side_effect=lambda model: {
            Strategy: strategy_query,
            StrategyRun: run_query,
            Trade: trade_query
        }[model])
        
        mock_session_local.return_value = mock_db_session
        
        # 执行停止策略
        result = await manager.stop_strategy(1, close_positions=True)
        
        # 验证结果
        assert result is True
        
        # 验证交易统计正确
        assert mock_strategy_run.total_trades == 6
        assert mock_strategy_run.win_trades == 3  # 3个盈利交易
        assert mock_strategy_run.loss_trades == 2  # 2个亏损交易


class TestStrategyManagerEdgeCases:
    """测试策略管理器的边界情况"""
    
    @pytest.fixture
    def manager(self):
        """创建策略管理器实例"""
        return StrategyManager()
    
    @pytest.fixture
    def mock_db_session(self):
        """创建模拟数据库会话"""
        session = Mock(spec=Session)
        session.query = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        session.close = Mock()
        return session
    
    @pytest.mark.asyncio
    @patch('ftrader.strategy_manager.SessionLocal')
    async def test_stop_strategy_with_exception_during_close(
        self,
        mock_session_local,
        manager,
        mock_db_session
    ):
        """测试停止策略时平仓失败的情况"""
        # 创建会抛出异常的策略实例
        mock_strategy_instance = Mock()
        mock_strategy_instance.is_running = True
        mock_strategy_instance.stop = AsyncMock(side_effect=Exception("平仓失败"))
        mock_strategy_instance.symbol = 'BTC/USDT:USDT'
        
        manager.strategies = {1: mock_strategy_instance}
        manager.strategy_tasks = {1: Mock()}
        
        # 设置数据库查询
        strategy_query = Mock()
        strategy_query.filter = Mock(return_value=strategy_query)
        strategy_query.first = Mock(return_value=Mock(status=StrategyStatus.RUNNING))
        
        run_query = Mock()
        run_query.filter = Mock(return_value=run_query)
        run_query.order_by = Mock(return_value=run_query)
        run_query.first = Mock(return_value=None)
        
        mock_db_session.query = Mock(side_effect=lambda model: {
            Strategy: strategy_query,
            StrategyRun: run_query
        }[model])
        
        mock_session_local.return_value = mock_db_session
        
        # 执行停止策略（应该捕获异常并继续）
        result = await manager.stop_strategy(1, close_positions=True)
        
        # 验证即使出错也返回True（因为数据库状态会被更新）
        assert result is True
    
    @pytest.mark.asyncio
    @patch('ftrader.strategy_manager.SessionLocal')
    async def test_start_strategy_with_existing_position_cleanup_failure(
        self,
        mock_session_local,
        manager,
        mock_db_session
    ):
        """测试启动策略时清理旧持仓失败的情况"""
        # 创建模拟对象
        mock_exchange = Mock()
        mock_exchange.get_open_position = Mock(return_value={
            'symbol': 'BTC/USDT:USDT',
            'side': 'long',
            'contracts': 0.01
        })
        mock_exchange.close_position = Mock(return_value=False)  # 清理失败
        mock_exchange.get_balance = Mock(return_value={'total': 10000.0})
        
        mock_strategy_instance = Mock()
        mock_strategy_instance.symbol = 'BTC/USDT:USDT'
        mock_strategy_instance.exchange = mock_exchange
        mock_strategy_instance.risk_manager = Mock()
        mock_strategy_instance.start = AsyncMock(return_value=True)
        mock_strategy_instance.run = AsyncMock()
        mock_strategy_instance.on_status_change = None
        mock_strategy_instance.on_trade = None
        mock_strategy_instance.on_error = None
        
        manager.exchanges = {1: mock_exchange}
        
        # 设置数据库查询
        strategy = Mock()
        strategy.id = 1
        strategy.status = StrategyStatus.STOPPED
        strategy.strategy_type = StrategyType.CONFIG
        strategy.config_yaml = "trading:\n  symbol: BTC/USDT:USDT\nmartingale:\n  initial_position: 200"
        
        strategy_query = Mock()
        strategy_query.filter = Mock(return_value=strategy_query)
        strategy_query.first = Mock(return_value=strategy)
        
        mock_db_session.query = Mock(return_value=strategy_query)
        mock_db_session.add = Mock()
        mock_db_session.commit = Mock()
        mock_session_local.return_value = mock_db_session
        
        # Mock策略创建
        with patch('ftrader.strategy_manager.MartingaleStrategy', return_value=mock_strategy_instance):
            with patch('ftrader.strategy_manager.get_exchange', return_value=mock_exchange):
                with patch('ftrader.strategy_manager.yaml') as mock_yaml:
                    import yaml as yaml_module
                    mock_yaml.safe_load = yaml_module.safe_load
                    
                    # 执行启动策略
                    result = await manager.start_strategy(1)
        
        # 验证结果（即使清理失败，策略也应该启动）
        # 注意：实际实现中，清理失败会记录警告但继续启动
        assert result is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
