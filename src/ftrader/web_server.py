"""FastAPI Web服务器"""

import logging
import sys
import asyncio
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from .database import init_db
from .api import strategies, account, websocket, templates, backtest
from .tasks import get_background_tasks
from .strategy_manager import get_strategy_manager

logger = logging.getLogger(__name__)


def setup_logging(log_level: str = "INFO"):
    """
    配置日志系统
    
    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
    """
    # 获取日志级别
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # 创建日志格式
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # 清除现有的处理器
    root_logger.handlers.clear()
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_formatter = logging.Formatter(log_format, date_format)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # 创建日志目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 创建文件处理器（策略日志）
    strategy_log_file = log_dir / "strategy.log"
    file_handler = logging.FileHandler(strategy_log_file, encoding='utf-8')
    file_handler.setLevel(level)
    file_formatter = logging.Formatter(log_format, date_format)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # 设置第三方库的日志级别（避免过多输出）
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("ccxt").setLevel(logging.WARNING)
    
    logger.info(f"日志系统已配置，级别: {log_level}，日志文件: {strategy_log_file}")

# 创建FastAPI应用
app = FastAPI(
    title="FTrader API",
    description="多策略交易系统API",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(strategies.router)
app.include_router(account.router)
app.include_router(websocket.router)
app.include_router(templates.router)
app.include_router(backtest.router)


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    # 配置日志（如果还没有配置）
    if not logging.getLogger().handlers:
        log_level = os.getenv("LOG_LEVEL", "INFO")
        setup_logging(log_level)
    
    # 设置WebSocket管理器的主事件循环
    from .api.websocket import manager
    try:
        manager.set_main_loop(asyncio.get_running_loop())
    except RuntimeError:
        pass
    
    logger.info("初始化数据库...")
    init_db()
    logger.info("数据库初始化完成")
    
    # 恢复策略状态（修复服务重启后的状态不一致问题）
    logger.info("恢复策略状态...")
    strategy_manager = get_strategy_manager()
    strategy_manager.recover_strategy_states()
    logger.info("策略状态恢复完成")
    
    # 启动后台任务
    background_tasks = get_background_tasks()
    await background_tasks.start()


@app.get("/")
async def root():
    """根路径"""
    return {"message": "FTrader API", "version": "1.0.0"}


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok"}


# 如果前端文件存在，提供静态文件服务
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "dist")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """提供前端文件"""
        file_path = os.path.join(frontend_dir, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        # 返回index.html用于SPA路由
        return FileResponse(os.path.join(frontend_dir, "index.html"))


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    # 停止后台任务
    background_tasks = get_background_tasks()
    await background_tasks.stop()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
