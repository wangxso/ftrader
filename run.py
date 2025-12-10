#!/usr/bin/env python3
"""便捷运行脚本"""

import sys
import os

# 获取脚本所在目录
script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(script_dir, 'src')

# 添加src目录到Python路径
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# 导入并运行主程序
try:
    from ftrader.main import main
except ImportError as e:
    print(f"导入错误: {e}")
    print(f"请确保已安装依赖: pip3 install ccxt pyyaml python-dotenv")
    print(f"或者安装项目: pip3 install -e .")
    sys.exit(1)

if __name__ == '__main__':
    main()

