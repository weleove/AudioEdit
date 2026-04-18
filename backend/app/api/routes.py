from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.models.job import JobRecord, OperationType
from app.schemas.job import JobCreateResponse, JobResponse
from app.services.job_service import JobService
from app.services.job_store import JobStore
from app.services.media_tools import MediaProcessingError, MediaProcessor


router = APIRouter(prefix="/api", tags=["audio"])

job_store = JobStore()
media_processor = MediaProcessor(settings)
job_service = JobService(settings=settings, store=job_store, processor=media_processor)


def serialize_job(job: JobRecord) -> JobResponse:
    download_url = f"/api/jobs/{job.id}/download" if job.status == "completed" and job.output_path else None
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
    return {"status": "ok"}


@router.post("/jobs", response_model=JobCreateResponse, status_code=202)
async def create_job(
    background_tasks: BackgroundTasks,
    operation: OperationType = Form(...),
    file: UploadFile = File(...),
) -> JobCreateResponse:
    filename = job_service.sanitize_filename(file.filename)
    try:
        media_processor.validate_extension(filename)
    except MediaProcessingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job_id = job_service.generate_job_id()
    input_path = settings.uploads_dir / job_id / filename

    await job_service.save_upload(file, input_path)
    job = job_service.create_job(job_id=job_id, operation=operation, filename=filename, input_path=input_path)
    background_tasks.add_task(job_service.process_job, job.id)

    return JobCreateResponse(job_id=job.id, status=job.status, message=job.message)


@router.get("/jobs", response_model=list[JobResponse])
def list_jobs() -> list[JobResponse]:
    return [serialize_job(job) for job in job_store.list()]


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return serialize_job(job)


@router.get("/jobs/{job_id}/download")
def download_result(job_id: str) -> FileResponse:
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if not job.output_path:
        raise HTTPException(status_code=400, detail="Result file is not ready yet.")

    output_path = Path(job.output_path)
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Result file does not exist.")

    return FileResponse(path=output_path, filename=job.output_name, media_type="application/octet-stream")
