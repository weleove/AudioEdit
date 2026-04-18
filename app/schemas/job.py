from __future__ import annotations

from pydantic import BaseModel

from app.models.job import JobStatus, OperationType


class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


class JobResponse(BaseModel):
    job_id: str
    operation: OperationType
    original_filename: str
    status: JobStatus
    message: str
    created_at: str
    updated_at: str
    error: str | None = None
    download_url: str | None = None

