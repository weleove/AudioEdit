from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


OperationType = Literal[
    "extract_instrumental",
    "extract_vocals",
    "denoise_audio",
    "extract_audio_from_video",
]

JobStatus = Literal["queued", "processing", "completed", "failed"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class JobRecord:
    id: str
    operation: OperationType
    filename: str
    input_key: str
    status: JobStatus = "queued"
    message: str = "Job created and waiting to start."
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    error: str | None = None
    output_key: str | None = None
    output_name: str | None = None

    def touch(self) -> None:
        self.updated_at = utc_now_iso()
