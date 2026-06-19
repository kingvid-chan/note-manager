"""FastAPI 应用入口 — 生命周期、中间件、路由挂载。"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .config import settings
from .database import engine, Base, get_db


class CacheControlMiddleware(BaseHTTPMiddleware):
    """对 HTML 响应强制设置 ``Cache-Control: no-cache`` HTTP 头。

    ADR-001 §4.4 要求：HTML 文档必须由服务器下发真实响应头，不能用 ``<meta>``。
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            response.headers["Cache-Control"] = "no-cache"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期 — 启动时创建表、可选种子数据。"""
    # 导入模型以确保它们注册到 Base.metadata
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # 可选种子数据
    if settings.SEED_DEMO:
        from .seed import seed_demo_data
        db = next(get_db())
        try:
            seed_demo_data(db)
        finally:
            db.close()

    yield


app = FastAPI(
    title="Note Manager",
    version="0.0.1",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)

# ── 中间件 ──────────────────────────────────────────────
app.add_middleware(CacheControlMiddleware)

# ── 健康检查（必须在 static mount 之前注册）──────────────
@app.get(f"{settings.BASE_PATH}/healthz")
async def healthz():
    """Kubernetes / 运维健康探针。"""
    return {"status": "ok"}

# ── API 路由 ────────────────────────────────────────────
from .routers import auth, notes  # noqa: E402
app.include_router(auth.router, prefix=f"{settings.BASE_PATH}/api/auth")
app.include_router(notes.router, prefix=f"{settings.BASE_PATH}/api/notes")

# ── 静态文件（最后注册，作为 fallback）────────────────────
static_dir = os.path.join(os.path.dirname(__file__), "..", "..", "static")
if os.path.isdir(static_dir):
    app.mount(
        f"{settings.BASE_PATH}/static",
        StaticFiles(directory=static_dir),
        name="static",
    )
