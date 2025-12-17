#!/bin/bash

# 重启脚本 - 停止并重新启动 ftrader web 服务

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "正在重启 ftrader web 服务..."

# 先停止服务
if [ -f "stop.sh" ]; then
    ./stop.sh
    sleep 2
else
    echo "警告: stop.sh 不存在，尝试直接启动..."
fi

# 再启动服务
if [ -f "start.sh" ]; then
    ./start.sh
else
    echo "错误: start.sh 不存在"
    exit 1
fi
