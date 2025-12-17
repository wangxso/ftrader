"""pytest mock 设置 - 必须在任何其他模块导入之前执行"""

import sys
from unittest.mock import MagicMock

# 在导入任何其他模块之前，立即设置 mock
# 这样可以避免在导入 conftest.py 时触发 ftrader/__init__.py 的导入

# Mock ccxt 相关模块（必须在 ccxt 被导入之前）
if 'ccxt' not in sys.modules:
    _mock_ccxt = MagicMock()
    sys.modules['ccxt'] = _mock_ccxt
    sys.modules['ccxt.base'] = MagicMock()
    sys.modules['ccxt.base.exchange'] = MagicMock()
    sys.modules['ccxt.base.exchange'].Exchange = MagicMock

# Mock cryptography 相关模块（必须在 cryptography 被导入之前）
if 'cryptography' not in sys.modules:
    _mock_crypto = MagicMock()
    sys.modules['cryptography'] = _mock_crypto
    sys.modules['cryptography.hazmat'] = MagicMock()
    sys.modules['cryptography.hazmat.primitives'] = MagicMock()
    sys.modules['cryptography.hazmat.primitives.hashes'] = MagicMock()
    sys.modules['cryptography.hazmat.bindings'] = MagicMock()
    sys.modules['cryptography.hazmat.bindings._rust'] = MagicMock()
    sys.modules['cryptography.hazmat.bindings._rust'].openssl = MagicMock()

# Mock ftrader.exchange 模块（避免导入 ccxt）
# 必须在 ftrader.exchange 被导入之前设置
if 'ftrader.exchange' not in sys.modules:
    _mock_exchange_module = MagicMock()
    _mock_exchange_module.BinanceExchange = MagicMock
    sys.modules['ftrader.exchange'] = _mock_exchange_module

# Mock ftrader.exchange_manager 模块
# 必须在 ftrader.exchange_manager 被导入之前设置
if 'ftrader.exchange_manager' not in sys.modules:
    _mock_exchange_manager_module = MagicMock()
    _mock_exchange_manager_module.get_exchange = MagicMock
    _mock_exchange_manager_module.get_exchange_manager = MagicMock
    _mock_exchange_manager_module.ExchangeManager = MagicMock
    sys.modules['ftrader.exchange_manager'] = _mock_exchange_manager_module
