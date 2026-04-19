from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings

# 创建 FastAPI 应用实例
app = FastAPI(
    title="AudioEdit API",
    version="0.1.0",
    description="Audio editing and media processing service",
)

# 添加 CORS 中间件，允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,  # 允许的前端源地址
    allow_credentials=True,  # 允许携带凭证
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
    expose_headers=["Content-Disposition"],  # 暴露 Content-Disposition 响应头用于文件下载
)

# 注册 API 路由
app.include_router(router)
