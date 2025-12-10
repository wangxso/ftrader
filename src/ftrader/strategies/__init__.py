"""策略模块"""

from .base import BaseStrategy
from .martingale import MartingaleStrategy

__all__ = [
    'BaseStrategy',
    'MartingaleStrategy',
]
