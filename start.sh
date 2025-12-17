#!/bin/bash

# 启动脚本 - 后台运行 ftrader web 服务

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 激活虚拟环境
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo "已激活虚拟环境"
else
    echo "错误: 虚拟环境不存在，请先运行 'uv sync' 或 'python -m venv .venv'"
    exit 1
fi

# 检查服务是否已经在运行
PID_FILE=".ftrader.pid"
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "服务已经在运行中 (PID: $OLD_PID)"
        echo "如需重启，请先运行 ./stop.sh"
        exit 1
    else
        # PID 文件存在但进程不存在，删除旧的 PID 文件
        rm -f "$PID_FILE"
    fi
fi

# 设置日志文件
LOG_FILE="ftrader.log"
NO_LOG_FILE="ftrader_nohup.log"

# 启动服务（后台运行）
echo "正在启动 ftrader web 服务..."
nohup python -m uvicorn ftrader.web_server:app --host 0.0.0.0 --port 8000 > "$NO_LOG_FILE" 2>&1 &
PID=$!

# 保存 PID
echo $PID > "$PID_FILE"

# 等待一下，检查进程是否成功启动
sleep 2
if ps -p "$PID" > /dev/null 2>&1; then
    echo "✓ 服务已成功启动"
    echo "  - PID: $PID"
    echo "  - 日志文件: $NO_LOG_FILE"
    echo "  - 访问地址: http://localhost:8000"
    echo "  - API 文档: http://localhost:8000/docs"
    echo ""
    echo "查看日志: tail -f $NO_LOG_FILE"
    echo "停止服务: ./stop.sh"
else
    echo "✗ 服务启动失败，请查看日志: $NO_LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi
