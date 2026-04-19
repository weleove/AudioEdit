from __future__ import annotations

from pydantic import BaseModel

from app.models.job import JobStatus, OperationType


class JobCreateResponse(BaseModel):
    """创建任务的响应模型"""
    job_id: str  # 任务 ID
    status: JobStatus  # 任务状态
    message: str  # 状态消息


class JobResponse(BaseModel):
    """任务详情的响应模型"""
    job_id: str  # 任务 ID
    operation: OperationType  # 操作类型
    original_filename: str  # 原始文件名
    status: JobStatus  # 任务状态
    message: str  # 状态消息
    created_at: str  # 创建时间
    updated_at: str  # 更新时间
    error: str | None = None  # 错误信息（如果有）
    download_url: str | None = None  # 下载链接（任务完成后可用）

