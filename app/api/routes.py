from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.config import settings
from app.models.job import JobRecord, OperationType
from app.schemas.job import JobCreateResponse, JobResponse
from app.services.binary_store import BinaryStoreError, build_binary_store
from app.services.job_service import JobService
from app.services.job_store import JobStore
from app.services.media_tools import MediaProcessingError, MediaProcessor

# 创建 API 路由器
router = APIRouter(prefix="/api", tags=["audio"])

# 初始化服务实例
job_store = JobStore()  # 任务存储
media_processor = MediaProcessor(settings)  # 媒体处理器
binary_store = build_binary_store(settings)  # 二进制存储（Redis 或内存）
job_service = JobService(settings=settings, store=job_store, processor=media_processor, binary_store=binary_store)  # 任务服务


def serialize_job(job: JobRecord) -> JobResponse:
    """将任务记录转换为响应模型"""
    download_url = f"/api/jobs/{job.id}/download" if job.status == "completed" and job.output_key else None
    return JobResponse(
        job_id=job.id,
        operation=job.operation,
        original_filename=job.filename,
        status=job.status,
        message=job.message,
        created_at=job.created_at,
        updated_at=job.updated_at,
        error=job.error,
        download_url=download_url,
    )


@router.get("/health")
def healthcheck() -> dict[str, str]:
    """健康检查接口"""
    return {"status": "ok"}


@router.post("/jobs", response_model=JobCreateResponse, status_code=202)
async def create_job(
    background_tasks: BackgroundTasks,
    operation: OperationType = Form(...),
    file: UploadFile = File(...),
) -> JobCreateResponse:
    """创建音频处理任务"""
    filename = job_service.sanitize_filename(file.filename)
    try:
        media_processor.validate_extension(filename)  # 验证文件扩展名
    except MediaProcessingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job_id = job_service.generate_job_id()  # 生成任务 ID
    input_key = job_service.build_upload_key(job_id)  # 生成上传文件的存储键

    try:
        await job_service.save_upload(file, input_key)  # 保存上传的文件
    except BinaryStoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    job = job_service.create_job(job_id=job_id, operation=operation, filename=filename, input_key=input_key)  # 创建任务记录
    background_tasks.add_task(job_service.process_job, job.id)  # 在后台处理任务

    return JobCreateResponse(job_id=job.id, status=job.status, message=job.message)


@router.get("/jobs", response_model=list[JobResponse])
def list_jobs() -> list[JobResponse]:
    """获取所有任务列表"""
    return [serialize_job(job) for job in job_store.list()]


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    """获取指定任务的详情"""
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return serialize_job(job)


@router.get("/jobs/{job_id}/download")
def download_result(job_id: str) -> Response:
    """下载任务处理结果"""
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if not job.output_key:
        raise HTTPException(status_code=400, detail="Result file is not ready yet.")

    try:
        output_bytes = binary_store.get_bytes(job.output_key)  # 从存储获取结果文件
    except BinaryStoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if output_bytes is None:
        raise HTTPException(status_code=404, detail="Result file does not exist.")

    output_name = job.output_name or Path(job.filename).name
    media_type = mimetypes.guess_type(output_name)[0] or "application/octet-stream"  # 推断 MIME 类型
    ascii_name = output_name.encode("ascii", "ignore").decode() or "download.bin"
    disposition = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(output_name)}"  # 设置文件名（支持 UTF-8）

    return Response(
        content=output_bytes,
        media_type=media_type,
        headers={"Content-Disposition": disposition},
    )
