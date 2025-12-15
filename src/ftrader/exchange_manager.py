"""交易所实例管理器（单例模式）"""

import os
import logging
from typing import Optional
from threading import Lock
from dotenv import load_dotenv

from .exchange import BinanceExchange

logger = logging.getLogger(__name__)

# 确保加载环境变量
load_dotenv()


class ExchangeManager:
    """交易所实例管理器（单例模式）"""
    
    _instance: Optional['ExchangeManager'] = None
    _lock: Lock = Lock()
    
    def __new__(cls):
        """单例模式实现"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ExchangeManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化管理器"""
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._exchange: Optional[BinanceExchange] = None
        self._config_hash: Optional[str] = None
        self._initialized = True
    
    def get_exchange(self, 
                     api_key: Optional[str] = None,
                     api_secret: Optional[str] = None,
                     testnet: Optional[bool] = None,
                     proxy: Optional[str] = None) -> BinanceExchange:
        """
        获取交易所实例（单例）
        
        Args:
            api_key: API密钥（如果为None，从环境变量读取）
            api_secret: API密钥（如果为None，从环境变量读取）
            testnet: 是否使用测试网（如果为None，从环境变量读取）
            proxy: 代理地址（如果为None，从环境变量读取）
        
        Returns:
            交易所实例
        """
        # 从环境变量读取配置（如果未提供）
        if testnet is None:
            testnet = os.getenv('BINANCE_TESTNET', 'False').lower() == 'true'
        
        if api_key is None or api_secret is None:
            if testnet:
                api_key = api_key or os.getenv('BINANCE_TESTNET_API_KEY') or os.getenv('BINANCE_API_KEY', '')
                api_secret = api_secret or os.getenv('BINANCE_TESTNET_SECRET_KEY') or os.getenv('BINANCE_SECRET_KEY', '')
            else:
                api_key = api_key or os.getenv('BINANCE_API_KEY', '')
                api_secret = api_secret or os.getenv('BINANCE_SECRET_KEY', '')
        
        if proxy is None:
            proxy = os.getenv('BINANCE_PROXY', '')
        
        # 生成配置哈希，用于判断是否需要重新创建实例
        config_hash = self._generate_config_hash(api_key, api_secret, testnet, proxy)
        
        # 如果已有实例且配置相同，直接返回
        if self._exchange is not None and self._config_hash == config_hash:
            return self._exchange
        
        # 创建新实例
        logger.info(f"创建交易所实例 (测试网: {testnet}, 代理: {'已配置' if proxy else '未配置'})")
        self._exchange = BinanceExchange(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
            proxy=proxy
        )
        self._config_hash = config_hash
        
        return self._exchange
    
    def _generate_config_hash(self, api_key: str, api_secret: str, testnet: bool, proxy: str) -> str:
        """
        生成配置哈希值
        
        Args:
            api_key: API密钥
            api_secret: API密钥
            testnet: 是否使用测试网
            proxy: 代理地址
        
        Returns:
            配置哈希值
        """
        # 使用配置的关键部分生成哈希（不包含完整的密钥，只用于区分配置）
        import hashlib
        config_str = f"{api_key[:8] if api_key else ''}_{api_secret[:8] if api_secret else ''}_{testnet}_{proxy}"
        return hashlib.md5(config_str.encode()).hexdigest()
    
    def reset(self):
        """重置实例（用于测试或重新配置）"""
        with self._lock:
            self._exchange = None
            self._config_hash = None


def get_exchange_manager() -> ExchangeManager:
    """
    获取交易所管理器单例
    
    Returns:
        交易所管理器实例
    """
    return ExchangeManager()


def get_exchange(api_key: Optional[str] = None,
                 api_secret: Optional[str] = None,
                 testnet: Optional[bool] = None,
                 proxy: Optional[str] = None) -> BinanceExchange:
    """
    便捷函数：获取交易所实例
    
    Args:
        api_key: API密钥（可选）
        api_secret: API密钥（可选）
        testnet: 是否使用测试网（可选）
        proxy: 代理地址（可选）
    
    Returns:
        交易所实例
    """
    manager = get_exchange_manager()
    return manager.get_exchange(api_key, api_secret, testnet, proxy)

