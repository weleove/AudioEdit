from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Settings:
    base_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parents[1])
    frontend_origins_raw: str = field(
        default_factory=lambda: os.getenv(
            "FRONTEND_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        )
    )
    max_upload_size_mb: int = field(default_factory=lambda: int(os.getenv("MAX_UPLOAD_SIZE_MB", "500")))
    demucs_model: str = field(default_factory=lambda: os.getenv("DEMUCS_MODEL", "htdemucs"))
    demucs_device: str = field(default_factory=lambda: os.getenv("DEMUCS_DEVICE", "cuda"))
    demucs_segment: str = field(default_factory=lambda: os.getenv("DEMUCS_SEGMENT", "7"))
    demucs_jobs: int = field(default_factory=lambda: int(os.getenv("DEMUCS_JOBS", "0")))
    ffmpeg_bin: str = field(default_factory=lambda: os.getenv("FFMPEG_BIN", "ffmpeg"))

    storage_dir: Path = field(init=False)
    uploads_dir: Path = field(init=False)
    outputs_dir: Path = field(init=False)
    work_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        self.storage_dir = self.base_dir / "storage"
        self.uploads_dir = self.storage_dir / "uploads"
        self.outputs_dir = self.storage_dir / "outputs"
        self.work_dir = self.storage_dir / "work"

    @property
    def frontend_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins_raw.split(",") if origin.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    def ensure_directories(self) -> None:
        for directory in (self.storage_dir, self.uploads_dir, self.outputs_dir, self.work_dir):
            directory.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
