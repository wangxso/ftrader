"""pytest 配置文件 - 用于设置测试环境"""

# 首先导入 mock 设置（必须在任何其他导入之前）
from . import _pytest_mock_setup  # noqa: F401

# 现在可以安全导入其他模块
