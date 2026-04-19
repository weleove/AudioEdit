from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.config import Settings
from app.models.job import JobRecord, OperationType
from app.services.binary_store import BinaryStore
from app.services.job_store import JobStore
from app.services.media_tools import MediaProcessingError, MediaProcessor


class JobService:
    """任务服务类，负责任务的创建、文件上传和处理流程"""
    def __init__(self, settings: Settings, store: JobStore, processor: MediaProcessor, binary_store: BinaryStore) -> None:
        self.settings = settings
        self.store = store  # 任务存储
        self.processor = processor  # 媒体处理器
        self.binary_store = binary_store  # 二进制存储

    def generate_job_id(self) -> str:
        """生成唯一的任务 ID"""
        return uuid4().hex

    def sanitize_filename(self, filename: str | None) -> str:
        """清理文件名，移除路径并替换空格"""
        candidate = Path(filename or "upload.bin").name
        return candidate.replace(" ", "_")

    def build_upload_key(self, job_id: str) -> str:
        """构建上传文件的存储键"""
        return f"upload:{job_id}"

    def build_output_key(self, job_id: str) -> str:
        """构建输出文件的存储键"""
        return f"output:{job_id}"

    async def save_upload(self, upload_file: UploadFile, storage_key: str) -> None:
        """保存上传的文件到存储，分块读取并检查大小限制"""
        self.binary_store.delete(storage_key)
        written = 0
        try:
            while True:
                chunk = await upload_file.read(1024 * 1024)  # 每次读取 1MB
                if not chunk:
                    break
                written += len(chunk)
                if written > self.settings.max_upload_size_bytes:
                    raise HTTPException(status_code=413, detail="Uploaded file exceeds the size limit.")
                self.binary_store.append_bytes(storage_key, chunk)
        except Exception:
            self.binary_store.delete(storage_key)  # 失败时清理
            raise
        finally:
            await upload_file.close()

    def create_job(self, job_id: str, operation: OperationType, filename: str, input_key: str) -> JobRecord:
        """创建任务记录"""
        return self.store.create(
            job_id=job_id,
            operation=operation,
            filename=filename,
            input_key=input_key,
        )

    def process_job(self, job_id: str) -> None:
        """处理任务的主流程：读取输入文件、执行操作、保存结果"""
        job = self.store.get(job_id)
        if not job:
            return

        output_key = self.build_output_key(job_id)
        temp_dir: Path | None = None

        try:
            self.store.update(job_id, status="processing", message="Processing started. Please wait.")
            source_bytes = self.binary_store.get_bytes(job.input_key)  # 从存储获取上传的文件
            if source_bytes is None:
                raise MediaProcessingError("Uploaded source file is missing or has expired from temporary storage.")

            # 创建临时工作目录
            temp_dir = self.settings.temp_root_dir / f"audioedit_{job_id}_{uuid4().hex}"
            temp_dir.mkdir(parents=True, exist_ok=True)
            working_dir = temp_dir / "work"
            working_dir.mkdir(parents=True, exist_ok=True)

            # 将输入文件写入临时目录
            input_path = temp_dir / self.sanitize_filename(job.filename)
            input_path.write_bytes(source_bytes)
            output_path = self._build_output_path(job.operation, temp_dir)

            # 根据操作类型执行相应的处理
            if job.operation == "extract_audio_from_video":
                self.processor.extract_audio_from_video(input_path, output_path)
            elif job.operation == "denoise_audio":
                normalized_path = self.processor.normalize_audio(input_path, working_dir)
                self.processor.denoise_audio(normalized_path, output_path)
            elif job.operation == "extract_vocals":
                normalized_path = self.processor.normalize_audio(input_path, working_dir)
                demucs_dir = working_dir / "demucs"
                result_path = self.processor.separate_stems(normalized_path, demucs_dir, stem="vocals")
                self.processor.copy_to_output(result_path, output_path)
            elif job.operation == "extract_instrumental":
                normalized_path = self.processor.normalize_audio(input_path, working_dir)
                demucs_dir = working_dir / "demucs"
                result_path = self.processor.separate_stems(normalized_path, demucs_dir, stem="instrumental")
                self.processor.copy_to_output(result_path, output_path)
            else:
                raise MediaProcessingError("Unknown operation type.")

            # 读取处理结果并保存到存储
            result_bytes = output_path.read_bytes()
            output_name = output_path.name

            self.binary_store.set_bytes(output_key, result_bytes)

            # 更新任务状态为完成
            self.store.update(
                job_id,
                status="completed",
                message="Processing completed. Result file is ready for download.",
                output_key=output_key,
                output_name=output_name,
            )
        except Exception as exc:
            # 处理失败时清理输出并更新状态
            self.binary_store.delete(output_key)
            self.store.update(
                job_id,
                status="failed",
                message="Processing failed.",
                error=str(exc),
            )
        finally:
            # 清理临时文件和输入文件
            self.binary_store.delete(job.input_key)
            if temp_dir is not None:
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _build_output_path(self, operation: OperationType, output_dir: Path) -> Path:
        """根据操作类型构建输出文件路径"""
        if operation == "extract_audio_from_video":
            return output_dir / "extracted_audio.mp3"
        if operation == "denoise_audio":
            return output_dir / "denoised.wav"
        if operation == "extract_vocals":
            return output_dir / "vocals.wav"
        return output_dir / "instrumental.wav"
