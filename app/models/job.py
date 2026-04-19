from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

# 操作类型：提取伴奏、提取人声、降噪、从视频提取音频
OperationType = Literal[
    "extract_instrumental",
    "extract_vocals",
    "denoise_audio",
    "extract_audio_from_video",
]

# 任务状态：排队中、处理中、已完成、失败
JobStatus = Literal["queued", "processing", "completed", "failed"]


def utc_now_iso() -> str:
    """返回当前 UTC 时间的 ISO 格式字符串"""
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class JobRecord:
    """任务记录数据模型"""
    id: str  # 任务唯一标识符
    operation: OperationType  # 操作类型
    filename: str  # 原始文件名
    input_key: str  # 输入文件在存储中的键
    status: JobStatus = "queued"  # 任务状态
    message: str = "Job created and waiting to start."  # 状态消息
    created_at: str = field(default_factory=utc_now_iso)  # 创建时间
    updated_at: str = field(default_factory=utc_now_iso)  # 更新时间
    error: str | None = None  # 错误信息
    output_key: str | None = None  # 输出文件在存储中的键
    output_name: str | None = None  # 输出文件名

    def touch(self) -> None:
        """更新任务的最后修改时间"""
        self.updated_at = utc_now_iso()
