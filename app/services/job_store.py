from __future__ import annotations

import copy
from threading import Lock

from app.models.job import JobRecord, OperationType


class JobStore:
    """任务存储类，使用内存存储任务记录（线程安全）"""
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}  # 任务字典
        self._lock = Lock()  # 线程锁

    def create(self, job_id: str, operation: OperationType, filename: str, input_key: str) -> JobRecord:
        """创建新任务"""
        job = JobRecord(id=job_id, operation=operation, filename=filename, input_key=input_key)
        with self._lock:
            self._jobs[job_id] = job
        return copy.deepcopy(job)

    def get(self, job_id: str) -> JobRecord | None:
        """根据 ID 获取任务"""
        with self._lock:
            job = self._jobs.get(job_id)
            return copy.deepcopy(job) if job else None

    def list(self) -> list[JobRecord]:
        """获取所有任务列表，按创建时间倒序排列"""
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda item: item.created_at, reverse=True)
            return [copy.deepcopy(job) for job in jobs]

    def update(self, job_id: str, **updates: object) -> JobRecord:
        """更新任务字段"""
        with self._lock:
            job = self._jobs[job_id]
            for key, value in updates.items():
                setattr(job, key, value)
            job.touch()  # 更新时间戳
            return copy.deepcopy(job)
