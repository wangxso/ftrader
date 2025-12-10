"""配置管理模块"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv


class Config:
    """配置管理类"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化配置
        
        Args:
            config_path: 配置文件路径
        """
        # 加载环境变量
        load_dotenv()
        
        # 读取配置文件
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
        
        # 验证配置
        self._validate_config()
    
    def _validate_config(self):
        """验证配置文件的完整性"""
        required_sections = ['trading', 'martingale', 'trigger', 'risk', 'monitoring']
        for section in required_sections:
            if section not in self._config:
                raise ValueError(f"配置文件缺少必需的节: {section}")
        
        # 验证交易配置
        trading = self._config['trading']
        if 'symbol' not in trading:
            raise ValueError("交易配置缺少 symbol")
        if 'side' not in trading or trading['side'] not in ['long', 'short']:
            raise ValueError("交易配置 side 必须是 'long' 或 'short'")
        if 'leverage' not in trading or trading['leverage'] < 1:
            raise ValueError("杠杆倍数必须 >= 1")
        
        # 验证马丁格尔参数
        martingale = self._config['martingale']
        if martingale['initial_position'] <= 0:
            raise ValueError("初始仓位必须 > 0")
        if martingale['multiplier'] <= 1:
            raise ValueError("加仓倍数必须 > 1")
        if martingale['max_additions'] < 0:
            raise ValueError("最大加仓次数必须 >= 0")
    
    @property
    def api_key(self) -> str:
        """获取币安API密钥"""
        # 优先使用测试网API密钥（如果设置了）
        if self.testnet:
            key = os.getenv('BINANCE_TESTNET_API_KEY') or os.getenv('BINANCE_API_KEY')
        else:
            key = os.getenv('BINANCE_API_KEY')
        
        # 测试网可以允许空密钥（某些测试网功能不需要密钥）
        if not key and not self.testnet:
            raise ValueError("未设置 BINANCE_API_KEY 环境变量")
        return key or ''
    
    @property
    def api_secret(self) -> str:
        """获取币安API密钥"""
        # 优先使用测试网API密钥（如果设置了）
        if self.testnet:
            secret = os.getenv('BINANCE_TESTNET_SECRET_KEY') or os.getenv('BINANCE_SECRET_KEY')
        else:
            secret = os.getenv('BINANCE_SECRET_KEY')
        
        # 测试网可以允许空密钥
        if not secret and not self.testnet:
            raise ValueError("未设置 BINANCE_SECRET_KEY 环境变量")
        return secret or ''
    
    @property
    def testnet(self) -> bool:
        """是否使用测试网"""
        return os.getenv('BINANCE_TESTNET', 'False').lower() == 'true'
    
    @property
    def symbol(self) -> str:
        """交易对"""
        return self._config['trading']['symbol']
    
    @property
    def side(self) -> str:
        """交易方向：long 或 short"""
        return self._config['trading']['side']
    
    @property
    def leverage(self) -> int:
        """杠杆倍数"""
        return int(self._config['trading']['leverage'])
    
    @property
    def initial_position(self) -> float:
        """初始仓位（USDT）"""
        return float(self._config['martingale']['initial_position'])
    
    @property
    def multiplier(self) -> float:
        """加仓倍数"""
        return float(self._config['martingale']['multiplier'])
    
    @property
    def max_additions(self) -> int:
        """最大加仓次数"""
        return int(self._config['martingale']['max_additions'])
    
    @property
    def price_drop_percent(self) -> float:
        """触发价格下跌百分比"""
        return float(self._config['trigger']['price_drop_percent'])
    
    @property
    def start_immediately(self) -> bool:
        """是否立即开始"""
        return self._config['trigger'].get('start_immediately', False)
    
    @property
    def stop_loss_percent(self) -> float:
        """止损百分比"""
        return float(self._config['risk']['stop_loss_percent'])
    
    @property
    def take_profit_percent(self) -> float:
        """止盈百分比"""
        return float(self._config['risk']['take_profit_percent'])
    
    @property
    def max_loss_percent(self) -> float:
        """最大亏损百分比"""
        return float(self._config['risk']['max_loss_percent'])
    
    @property
    def check_interval(self) -> int:
        """价格检查间隔（秒）"""
        return int(self._config['monitoring']['check_interval'])
    
    @property
    def price_precision(self) -> int:
        """价格精度"""
        return int(self._config['monitoring']['price_precision'])
    
    def get_config(self) -> Dict[str, Any]:
        """获取完整配置字典"""
        return self._config.copy()

