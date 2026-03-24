"""
FastAPI 主应用入口
"""
from contextlib import asynccontextmanager
from pathlib import Path
import subprocess
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.db.database import init_db
from app.api.routers import _auth, _product, _order, _address, _ai, _admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化数据库
    print("🚀 正在初始化数据库...")
    await init_db()
    await seed_demo_data()
    print("✅ 数据库初始化完成")
    
    yield
    
    # 关闭时清理资源
    print("👋 应用正在关闭...")


async def seed_demo_data():
    """
    初始化演示数据。

    这里直接复用 scripts/init_db.py，保持“表结构 + 管理员 + 分类 + 商品”的初始化逻辑
    只有一份，避免 app 启动逻辑和脚本逻辑分叉。
    """
    project_root = Path(__file__).resolve().parents[1]
    subprocess.run(
        [sys.executable, "scripts/init_db.py"],
        cwd=str(project_root),
        check=True,
    )


# 创建 FastAPI 应用实例
app = FastAPI(
    title=settings.APP_NAME,
    description="基于 FastAPI + OpenAI 的 AI 驱动电商后端系统",
    version="1.0.0",
    lifespan=lifespan,
)

# ==================== 静态文件（上传资源） ====================

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


# ==================== CORS 配置 ====================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 路由注册 ====================
# 统一为所有业务接口添加 /api 前缀，前端可稳定使用 /api/* 访问后端
# 例如：/api/auth/login、/api/products、/api/orders
for router in (
    _auth.router,
    _product.router,
    _order.router,
    _address.router,
    _ai.router,
    _admin.router,
):
    app.include_router(router, prefix="/api")


# ==================== 根路径 ====================

@app.get("/")
async def root():
    """API 根路径"""
    return {
        "message": f"欢迎使用 {settings.APP_NAME} API",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": "1.0.0"
    }


# ==================== 错误处理 ====================

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """统一处理 Pydantic 验证错误"""
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(x) for x in error["loc"])
        message = error["msg"]
        errors.append(f"{field}: {message}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "请求参数验证失败",
            "errors": errors
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
