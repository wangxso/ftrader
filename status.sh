#!/bin/bash

# 状态检查脚本 - 检查 ftrader web 服务运行状态

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE=".ftrader.pid"

echo "=== FTrader 服务状态 ==="
echo ""

# 检查 PID 文件
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "✓ 服务正在运行"
        echo "  - PID: $PID"
        
        # 显示进程信息
        ps -p "$PID" -o pid,ppid,user,%cpu,%mem,etime,cmd | tail -n 1
        
        # 检查端口
        if lsof -i :8000 > /dev/null 2>&1; then
            echo "  - 端口 8000: 已监听"
        else
            echo "  - 端口 8000: 未监听（可能有问题）"
        fi
        
        # 显示日志文件大小
        if [ -f "ftrader_nohup.log" ]; then
            LOG_SIZE=$(du -h ftrader_nohup.log | cut -f1)
            echo "  - 日志文件: ftrader_nohup.log ($LOG_SIZE)"
        fi
    else
        echo "✗ 服务未运行（PID 文件存在但进程不存在）"
        echo "  建议运行: rm -f $PID_FILE"
    fi
else
    # 尝试查找进程
    PIDS=$(pgrep -f "uvicorn ftrader.web_server:app")
    if [ -n "$PIDS" ]; then
        echo "⚠ 发现运行中的进程但无 PID 文件:"
        for PID in $PIDS; do
            ps -p "$PID" -o pid,ppid,user,%cpu,%mem,etime,cmd | tail -n 1
        done
    else
        echo "✗ 服务未运行"
    fi
fi

echo ""
echo "管理命令:"
echo "  启动: ./start.sh"
echo "  停止: ./stop.sh"
echo "  重启: ./restart.sh"
echo "  查看日志: tail -f ftrader_nohup.log"
