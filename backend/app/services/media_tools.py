from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from app.config import Settings

try:
    import torch
except Exception:  # pragma: no cover - torch import errors depend on runtime environment
    torch = None


class MediaProcessingError(RuntimeError):
    pass


class MediaProcessor:
    allowed_extensions = {
        ".mp3",
        ".wav",
        ".flac",
        ".ogg",
        ".aac",
        ".m4a",
        ".mp4",
        ".mov",
        ".avi",
        ".mkv",
        ".webm",
    }

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def validate_extension(self, filename: str) -> None:
        suffix = Path(filename).suffix.lower()
        if suffix not in self.allowed_extensions:
            allowed = ", ".join(sorted(self.allowed_extensions))
            raise MediaProcessingError(f"Unsupported file type. Allowed extensions: {allowed}")

    def normalize_audio(self, source_path: Path, working_dir: Path) -> Path:
        normalized_path = working_dir / "normalized.wav"
        self._run_command(
            [
                self.settings.ffmpeg_bin,
                "-y",
                "-i",
                str(source_path),
                "-vn",
                "-ac",
                "2",
                "-ar",
                "44100",
                "-c:a",
                "pcm_s16le",
                str(normalized_path),
            ],
            "Audio normalization failed",
        )
        return normalized_path

    def extract_audio_from_video(self, source_path: Path, output_path: Path) -> None:
        self._run_command(
            [
                self.settings.ffmpeg_bin,
                "-y",
                "-i",
                str(source_path),
                "-vn",
                "-acodec",
                "libmp3lame",
                "-q:a",
                "2",
                str(output_path),
            ],
            "Audio extraction from video failed",
        )

    def denoise_audio(self, source_path: Path, output_path: Path) -> None:
        self._run_command(
            [
                self.settings.ffmpeg_bin,
                "-y",
                "-i",
                str(source_path),
                "-af",
                "afftdn=nf=-25:tn=1",
                "-c:a",
                "pcm_s16le",
                str(output_path),
            ],
            "Noise reduction failed",
        )

    def separate_stems(self, source_path: Path, output_dir: Path, stem: str) -> Path:
        command = [
            sys.executable,
            "-m",
            "demucs",
            "--two-stems",
            "vocals",
            "--name",
            self.settings.demucs_model,
            "--out",
            str(output_dir),
            "-d",
            self._resolve_demucs_device(),
        ]

        segment = self.settings.demucs_segment.strip()
        if segment:
            command.extend(["--segment", segment])

        if self.settings.demucs_jobs > 0:
            command.extend(["-j", str(self.settings.demucs_jobs)])

        command.append(str(source_path))
        self._run_command(command, "Stem separation failed")

        target_name = "vocals.wav" if stem == "vocals" else "no_vocals.wav"
        matches = sorted(output_dir.rglob(target_name))
        if not matches:
            raise MediaProcessingError(f"Expected output file was not found: {target_name}")

        return matches[0]

    def copy_to_output(self, source_path: Path, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, output_path)

    def _run_command(self, command: list[str], title: str) -> None:
        env = self._build_command_env()
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
            env=env,
        )
        if completed.returncode == 0:
            return

        detail = completed.stderr.strip() or completed.stdout.strip() or "No extra error output was returned."
        detail = self._simplify_error_detail(detail)
        raise MediaProcessingError(f"{title}: {detail}")

    def _build_command_env(self) -> dict[str, str]:
        env = os.environ.copy()
        ffmpeg_bin = self.settings.ffmpeg_bin.strip()
        ffmpeg_path = Path(ffmpeg_bin)

        if ffmpeg_path.suffix.lower() == ".exe" and ffmpeg_path.parent.exists():
            current_path = env.get("PATH", "")
            env["PATH"] = str(ffmpeg_path.parent) if not current_path else f"{ffmpeg_path.parent}{os.pathsep}{current_path}"

        return env

    def _resolve_demucs_device(self) -> str:
        requested = self.settings.demucs_device.strip().lower() or "auto"
        if requested not in {"auto", "cpu", "cuda"}:
            raise MediaProcessingError(
                "Invalid DEMUCS_DEVICE value. Supported values are: auto, cpu, cuda."
            )

        cuda_available, runtime_detail = self._detect_cuda_runtime()
        if requested == "auto":
            return "cuda" if cuda_available else "cpu"

        if requested == "cuda" and not cuda_available:
            raise MediaProcessingError(
                "DEMUCS_DEVICE is set to cuda, but CUDA is not available in the backend environment. "
                f"{runtime_detail}"
            )

        return requested

    def _detect_cuda_runtime(self) -> tuple[bool, str]:
        if torch is None:
            return False, "PyTorch could not be imported, so CUDA cannot be used."

        cuda_available = bool(torch.cuda.is_available())
        torch_version = getattr(torch, "__version__", "unknown")
        cuda_version = getattr(getattr(torch, "version", None), "cuda", None) or "none"

        if cuda_available:
            try:
                device_name = torch.cuda.get_device_name(0)
            except Exception:
                device_name = "unknown GPU"
            return True, f"Detected torch {torch_version} with CUDA {cuda_version} on {device_name}."

        if "+cpu" in torch_version or cuda_version == "none":
            return False, (
                f"Detected torch {torch_version}, which does not expose CUDA in this environment. "
                "This usually means a CPU-only PyTorch build is installed."
            )

        return False, f"Detected torch {torch_version}, but torch.cuda.is_available() returned False."

    def _simplify_error_detail(self, detail: str) -> str:
        normalized_detail = detail.lower()

        if "ffmpeg is not installed" in normalized_detail:
            ffmpeg_hint = (
                "Demucs could not find FFmpeg. "
                "Make sure FFMPEG_BIN points to ffmpeg.exe and that the ffmpeg bin directory is available to child processes."
            )

            ffmpeg_path = Path(self.settings.ffmpeg_bin.strip())
            if ffmpeg_path.suffix.lower() == ".exe":
                return f"{ffmpeg_hint} Current FFMPEG_BIN: {ffmpeg_path}"

            return ffmpeg_hint

        return detail
