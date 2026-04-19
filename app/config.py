from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Settings:
    """应用配置类，从环境变量读取配置参数"""
    base_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parents[1])  # 项目根目录
    frontend_origins_raw: str = field(  # 允许的前端源地址（逗号分隔）
        default_factory=lambda: os.getenv(
            "FRONTEND_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        )
    )
    max_upload_size_mb: int = field(default_factory=lambda: int(os.getenv("MAX_UPLOAD_SIZE_MB", "500")))  # 最大上传文件大小（MB）
    demucs_model: str = field(default_factory=lambda: os.getenv("DEMUCS_MODEL", "htdemucs"))  # Demucs 模型名称
    demucs_device: str = field(default_factory=lambda: os.getenv("DEMUCS_DEVICE", "cuda"))  # Demucs 运行设备（cuda/cpu）
    demucs_segment: str = field(default_factory=lambda: os.getenv("DEMUCS_SEGMENT", "7"))  # Demucs 分段大小（秒）
    demucs_jobs: int = field(default_factory=lambda: int(os.getenv("DEMUCS_JOBS", "0")))  # Demucs 并行任务数（0=自动）
    ffmpeg_bin: str = field(default_factory=lambda: os.getenv("FFMPEG_BIN", "ffmpeg"))  # FFmpeg 可执行文件路径
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", ""))  # Redis 连接 URL（为空则使用内存存储）
    binary_key_prefix: str = field(default_factory=lambda: os.getenv("BINARY_KEY_PREFIX", "audioedit"))  # 二进制存储键前缀
    binary_ttl_seconds: int = field(default_factory=lambda: int(os.getenv("BINARY_TTL_SECONDS", "3600")))  # 二进制数据过期时间（秒）
    temp_root_raw: str = field(  # 临时工作目录
        default_factory=lambda: os.getenv(
            "TEMP_WORK_DIR",
            tempfile.gettempdir(),
        )
    )

    temp_root_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        """初始化后处理，将临时目录字符串转换为 Path 对象"""
        self.temp_root_dir = Path(self.temp_root_raw)

    @property
    def frontend_origins(self) -> list[str]:
        """解析前端源地址列表"""
        return [origin.strip() for origin in self.frontend_origins_raw.split(",") if origin.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        """将上传大小从 MB 转换为字节"""
        return self.max_upload_size_mb * 1024 * 1024

    def ensure_directories(self) -> None:
        """确保必要的目录存在"""
        self.temp_root_dir.mkdir(parents=True, exist_ok=True)


# 创建全局配置实例并初始化目录
settings = Settings()
settings.ensure_directories()
