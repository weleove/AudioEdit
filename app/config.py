from __future__ import annotations

import os
import tempfile
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
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", ""))
    binary_key_prefix: str = field(default_factory=lambda: os.getenv("BINARY_KEY_PREFIX", "audioedit"))
    binary_ttl_seconds: int = field(default_factory=lambda: int(os.getenv("BINARY_TTL_SECONDS", "3600")))
    temp_root_raw: str = field(
        default_factory=lambda: os.getenv(
            "TEMP_WORK_DIR",
            tempfile.gettempdir(),
        )
    )

    temp_root_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        self.temp_root_dir = Path(self.temp_root_raw)

    @property
    def frontend_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins_raw.split(",") if origin.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    def ensure_directories(self) -> None:
        self.temp_root_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
