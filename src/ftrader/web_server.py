"""FastAPI Web服务器"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from .database import init_db
from .api import strategies, account, websocket, templates
from .tasks import get_background_tasks

logger = logging.getLogger(__name__)

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


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("初始化数据库...")
    init_db()
    logger.info("数据库初始化完成")
    
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
