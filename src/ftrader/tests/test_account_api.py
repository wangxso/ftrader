"""账户API单元测试"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from httpx import AsyncClient
from fastapi import FastAPI, HTTPException
import os

from ftrader.api.account import router, get_balance
from ftrader.exchange import BinanceExchange
from ftrader.strategy_manager import StrategyManager


class TestGetBalance:
    """测试获取余额接口"""
    
    @pytest.fixture
    def mock_strategy_manager(self):
        """创建模拟的策略管理器"""
        manager = Mock(spec=StrategyManager)
        manager.exchanges = {}
        return manager
    
    @pytest.fixture
    def mock_exchange(self):
        """创建模拟的交易所实例"""
        exchange = Mock(spec=BinanceExchange)
        exchange.get_balance.return_value = {
            'free': 1000.0,
            'used': 200.0,
            'total': 1200.0
        }
        return exchange
    
    @pytest.mark.asyncio
    @patch('ftrader.api.account.get_strategy_manager')
    async def test_get_balance_with_existing_exchange(
        self, 
        mock_get_manager, 
        mock_strategy_manager, 
        mock_exchange
    ):
        """测试当策略管理器中有交易所实例时获取余额"""
        # 设置模拟对象
        mock_strategy_manager.exchanges = {1: mock_exchange}
        mock_get_manager.return_value = mock_strategy_manager
        
        # 调用接口
        result = await get_balance()
        
        # 验证结果
        assert result == {
            'total': 1200.0,
            'free': 1000.0,
            'used': 200.0
        }
        # 验证调用了交易所的 get_balance 方法
        mock_exchange.get_balance.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('ftrader.api.account.get_strategy_manager')
    @patch.dict(os.environ, {
        'BINANCE_API_KEY': 'test_api_key',
        'BINANCE_SECRET_KEY': 'test_secret_key',
        'BINANCE_TESTNET': 'False'
    })
    @patch('ftrader.api.account.BinanceExchange')
    async def test_get_balance_without_exchange_creates_new(
        self,
        mock_binance_exchange_class,
        mock_get_manager,
        mock_strategy_manager,
        mock_exchange
    ):
        """测试当策略管理器中没有交易所实例时创建新的交易所"""
        # 设置模拟对象
        mock_strategy_manager.exchanges = {}
        mock_get_manager.return_value = mock_strategy_manager
        mock_binance_exchange_class.return_value = mock_exchange
        
        # 调用接口
        result = await get_balance()
        
        # 验证结果
        assert result == {
            'total': 1200.0,
            'free': 1000.0,
            'used': 200.0
        }
        # 验证创建了新的交易所实例
        mock_binance_exchange_class.assert_called_once_with(
            'test_api_key',
            'test_secret_key',
            testnet=False
        )
        mock_exchange.get_balance.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('ftrader.api.account.get_strategy_manager')
    @patch.dict(os.environ, {
        'BINANCE_TESTNET_API_KEY': 'test_testnet_key',
        'BINANCE_TESTNET_SECRET_KEY': 'test_testnet_secret',
        'BINANCE_TESTNET': 'True'
    })
    @patch('ftrader.api.account.BinanceExchange')
    async def test_get_balance_with_testnet(
        self,
        mock_binance_exchange_class,
        mock_get_manager,
        mock_strategy_manager,
        mock_exchange
    ):
        """测试使用测试网模式获取余额"""
        # 设置模拟对象
        mock_strategy_manager.exchanges = {}
        mock_get_manager.return_value = mock_strategy_manager
        mock_binance_exchange_class.return_value = mock_exchange
        
        # 调用接口
        result = await get_balance()
        
        # 验证结果
        assert result == {
            'total': 1200.0,
            'free': 1000.0,
            'used': 200.0
        }
        # 验证使用测试网配置创建交易所
        mock_binance_exchange_class.assert_called_once_with(
            'test_testnet_key',
            'test_testnet_secret',
            testnet=True
        )
    
    @pytest.mark.asyncio
    @patch('ftrader.api.account.get_strategy_manager')
    @patch.dict(os.environ, {
        'BINANCE_TESTNET': 'False'
    }, clear=True)
    async def test_get_balance_without_api_keys_raises_exception(
        self,
        mock_get_manager,
        mock_strategy_manager
    ):
        """测试当没有API密钥时抛出异常"""
        # 设置模拟对象
        mock_strategy_manager.exchanges = {}
        mock_get_manager.return_value = mock_strategy_manager
        
        # 验证抛出异常
        with pytest.raises(HTTPException) as exc_info:
            await get_balance()
        
        assert exc_info.value.status_code == 500
        assert "未配置API密钥" in exc_info.value.detail
    
    @pytest.mark.asyncio
    @patch('ftrader.api.account.get_strategy_manager')
    async def test_get_balance_exchange_error_returns_default(
        self,
        mock_get_manager,
        mock_strategy_manager,
        mock_exchange
    ):
        """测试当交易所获取余额失败时返回默认值"""
        # 设置模拟对象，让 get_balance 抛出异常
        mock_strategy_manager.exchanges = {1: mock_exchange}
        mock_get_manager.return_value = mock_strategy_manager
        mock_exchange.get_balance.side_effect = Exception("网络错误")
        
        # 调用接口
        result = await get_balance()
        
        # 验证返回默认值（account.py 中的异常处理会捕获异常并返回默认值）
        assert result == {
            'free': 0.0,
            'used': 0.0,
            'total': 0.0
        }
        # 验证调用了 get_balance 方法
        mock_exchange.get_balance.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('ftrader.api.account.get_strategy_manager')
    async def test_get_balance_different_balance_values(
        self,
        mock_get_manager,
        mock_strategy_manager,
        mock_exchange
    ):
        """测试不同的余额值"""
        # 设置不同的余额值
        mock_exchange.get_balance.return_value = {
            'free': 5000.5,
            'used': 1000.25,
            'total': 6000.75
        }
        mock_strategy_manager.exchanges = {1: mock_exchange}
        mock_get_manager.return_value = mock_strategy_manager
        
        # 调用接口
        result = await get_balance()
        
        # 验证结果
        assert result == {
            'total': 6000.75,
            'free': 5000.5,
            'used': 1000.25
        }


class TestGetBalanceIntegration:
    """集成测试：使用 FastAPI TestClient 测试完整请求"""
    
    @pytest.fixture
    def app(self):
        """创建 FastAPI 应用"""
        app = FastAPI()
        app.include_router(router)
        return app
    
    @pytest.fixture
    def client(self, app):
        """创建测试客户端"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_strategy_manager(self):
        """创建模拟的策略管理器"""
        manager = Mock(spec=StrategyManager)
        manager.exchanges = {}
        return manager
    
    @pytest.fixture
    def mock_exchange(self):
        """创建模拟的交易所实例"""
        exchange = Mock(spec=BinanceExchange)
        exchange.get_balance.return_value = {
            'free': 1000.0,
            'used': 200.0,
            'total': 1200.0
        }
        return exchange
    
    @patch('ftrader.api.account.get_strategy_manager')
    def test_get_balance_endpoint_success(
        self,
        mock_get_manager,
        client,
        mock_strategy_manager,
        mock_exchange
    ):
        """测试获取余额端点成功响应"""
        mock_strategy_manager.exchanges = {1: mock_exchange}
        mock_get_manager.return_value = mock_strategy_manager
        mock_exchange.get_balance.return_value = {
            'free': 1000.0,
            'used': 200.0,
            'total': 1200.0
        }
        
        # 发送请求
        response = client.get("/api/account/balance")
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data == {
            'total': 1200.0,
            'free': 1000.0,
            'used': 200.0
        }
    
    @patch('ftrader.api.account.get_strategy_manager')
    @patch.dict(os.environ, {
        'BINANCE_TESTNET': 'False'
    }, clear=True)
    def test_get_balance_endpoint_no_api_keys(
        self,
        mock_get_manager,
        client,
        mock_strategy_manager
    ):
        """测试获取余额端点没有API密钥时的错误响应"""
        mock_strategy_manager.exchanges = {}
        mock_get_manager.return_value = mock_strategy_manager
        
        # 发送请求
        response = client.get("/api/account/balance")
        
        # 验证响应
        assert response.status_code == 500
        data = response.json()
        assert "未配置API密钥" in data['detail']

