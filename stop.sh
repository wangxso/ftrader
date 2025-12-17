#!/bin/bash

# 停止脚本 - 停止 ftrader web 服务

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE=".ftrader.pid"

# 检查 PID 文件是否存在
if [ ! -f "$PID_FILE" ]; then
    echo "PID 文件不存在，尝试查找运行中的进程..."
    
    # 尝试通过进程名查找
    PIDS=$(pgrep -f "uvicorn ftrader.web_server:app")
    if [ -z "$PIDS" ]; then
        echo "未找到运行中的 ftrader 服务"
        exit 0
    else
        echo "找到运行中的进程: $PIDS"
        for PID in $PIDS; do
            echo "正在停止进程 $PID..."
            kill "$PID" 2>/dev/null
        done
        sleep 2
        
        # 检查是否还有进程在运行
        REMAINING=$(pgrep -f "uvicorn ftrader.web_server:app")
        if [ -n "$REMAINING" ]; then
            echo "强制停止剩余进程..."
            for PID in $REMAINING; do
                kill -9 "$PID" 2>/dev/null
            done
        fi
        
        echo "✓ 服务已停止"
        exit 0
    fi
fi

# 读取 PID
PID=$(cat "$PID_FILE")

# 检查进程是否存在
if ! ps -p "$PID" > /dev/null 2>&1; then
    echo "进程 $PID 不存在，可能已经停止"
    rm -f "$PID_FILE"
    exit 0
fi

# 停止进程
echo "正在停止服务 (PID: $PID)..."
kill "$PID" 2>/dev/null

# 等待进程结束
for i in {1..10}; do
    if ! ps -p "$PID" > /dev/null 2>&1; then
        echo "✓ 服务已成功停止"
        rm -f "$PID_FILE"
        exit 0
    fi
    sleep 1
done

# 如果还在运行，强制停止
if ps -p "$PID" > /dev/null 2>&1; then
    echo "进程未响应，强制停止..."
    kill -9 "$PID" 2>/dev/null
    sleep 1
    
    if ! ps -p "$PID" > /dev/null 2>&1; then
        echo "✓ 服务已强制停止"
        rm -f "$PID_FILE"
    else
        echo "✗ 无法停止服务，请手动检查进程 $PID"
        exit 1
    fi
fi
