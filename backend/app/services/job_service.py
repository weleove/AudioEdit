from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.config import Settings
from app.models.job import JobRecord, OperationType
from app.services.job_store import JobStore
from app.services.media_tools import MediaProcessingError, MediaProcessor


class JobService:
    def __init__(self, settings: Settings, store: JobStore, processor: MediaProcessor) -> None:
        self.settings = settings
        self.store = store
        self.processor = processor

    def generate_job_id(self) -> str:
        return uuid4().hex

    def sanitize_filename(self, filename: str | None) -> str:
        candidate = Path(filename or "upload.bin").name
        return candidate.replace(" ", "_")

    async def save_upload(self, upload_file: UploadFile, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        try:
            with destination.open("wb") as file_handle:
                while True:
                    chunk = await upload_file.read(1024 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > self.settings.max_upload_size_bytes:
                        raise HTTPException(status_code=413, detail="Uploaded file exceeds the size limit.")
                    file_handle.write(chunk)
        except Exception:
            if destination.exists():
                destination.unlink()
            raise
        finally:
            await upload_file.close()

    def create_job(self, job_id: str, operation: OperationType, filename: str, input_path: Path) -> JobRecord:
        return self.store.create(
            job_id=job_id,
            operation=operation,
            filename=filename,
            input_path=str(input_path),
        )

    def process_job(self, job_id: str) -> None:
        job = self.store.get(job_id)
        if not job:
            return

        working_dir = self.settings.work_dir / job_id
        output_dir = self.settings.outputs_dir / job_id
        working_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            self.store.update(job_id, status="processing", message="Processing started. Please wait.")
            input_path = Path(job.input_path)
            output_path = self._build_output_path(job.operation, output_dir)

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

            self.store.update(
                job_id,
                status="completed",
                message="Processing completed. Result file is ready for download.",
                output_path=str(output_path),
                output_name=output_path.name,
            )
        except Exception as exc:
            self.store.update(
                job_id,
                status="failed",
                message="Processing failed.",
                error=str(exc),
            )

    def _build_output_path(self, operation: OperationType, output_dir: Path) -> Path:
        if operation == "extract_audio_from_video":
            return output_dir / "extracted_audio.mp3"
        if operation == "denoise_audio":
            return output_dir / "denoised.wav"
        if operation == "extract_vocals":
            return output_dir / "vocals.wav"
        return output_dir / "instrumental.wav"
