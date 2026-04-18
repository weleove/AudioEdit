from __future__ import annotations

import copy
from threading import Lock

from app.models.job import JobRecord, OperationType


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()

    def create(self, job_id: str, operation: OperationType, filename: str, input_key: str) -> JobRecord:
        job = JobRecord(id=job_id, operation=operation, filename=filename, input_key=input_key)
        with self._lock:
            self._jobs[job_id] = job
        return copy.deepcopy(job)

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return copy.deepcopy(job) if job else None

    def list(self) -> list[JobRecord]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda item: item.created_at, reverse=True)
            return [copy.deepcopy(job) for job in jobs]

    def update(self, job_id: str, **updates: object) -> JobRecord:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in updates.items():
                setattr(job, key, value)
            job.touch()
            return copy.deepcopy(job)
