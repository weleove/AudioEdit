from __future__ import annotations

import os
import shutil
import subprocess
import wave
from pathlib import Path

from app.config import Settings

try:
    import numpy as np
    import torch
except Exception:  # pragma: no cover - torch import errors depend on runtime environment
    np = None
    torch = None


class MediaProcessingError(RuntimeError):
    pass


class MediaProcessor:
    transformer_max_segment = 7.8
    safe_default_segment = 7.5
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
        if torch is None or np is None:
            raise MediaProcessingError(
                "Demucs dependencies are not available in the backend environment."
            )

        try:
            from demucs.apply import BagOfModels, apply_model
            from demucs.htdemucs import HTDemucs
            from demucs.pretrained import get_model
        except Exception as exc:  # pragma: no cover - depends on runtime environment
            raise MediaProcessingError(f"Failed to import Demucs runtime: {exc}") from exc

        if stem not in {"vocals", "instrumental"}:
            raise MediaProcessingError("Invalid stem selection. Supported values are vocals and instrumental.")

        device = self._resolve_demucs_device()
        segment = self._resolve_demucs_segment()
        segment_value = float(segment) if segment is not None else None

        try:
            model = get_model(name=self.settings.demucs_model)
        except Exception as exc:
            raise MediaProcessingError(f"Failed to load Demucs model '{self.settings.demucs_model}': {exc}") from exc

        max_allowed_segment = float("inf")
        if isinstance(model, HTDemucs):
            max_allowed_segment = float(model.segment)
        elif isinstance(model, BagOfModels):
            max_allowed_segment = model.max_allowed_segment

        if segment_value is not None and segment_value > max_allowed_segment:
            segment_value = min(self.safe_default_segment, max_allowed_segment)

        wav_tensor, sample_rate = self._load_pcm_wav(source_path)
        if sample_rate != int(getattr(model, "samplerate", sample_rate)):
            raise MediaProcessingError(
                f"Unexpected sample rate for Demucs input: {sample_rate}. "
                f"Expected {getattr(model, 'samplerate', sample_rate)}."
            )

        ref = wav_tensor.mean(0)
        mean = ref.mean()
        std = ref.std()
        if float(std) <= 1e-8:
            raise MediaProcessingError("Input audio appears silent after normalization and cannot be separated.")

        normalized = (wav_tensor - mean) / std

        with torch.no_grad():
            sources = apply_model(
                model,
                normalized[None],
                device=device,
                shifts=1,
                split=True,
                overlap=0.25,
                progress=False,
                num_workers=max(self.settings.demucs_jobs, 0),
                segment=segment_value,
            )[0]

        sources = sources * std + mean
        source_names = list(getattr(model, "sources", []))
        if "vocals" not in source_names:
            raise MediaProcessingError("The selected Demucs model does not expose a vocals stem.")

        vocals_index = source_names.index("vocals")
        vocals = sources[vocals_index]
        instrumental = torch.zeros_like(vocals)
        for index, name in enumerate(source_names):
            if name != "vocals":
                instrumental += sources[index]

        output_dir.mkdir(parents=True, exist_ok=True)
        vocals_path = output_dir / "vocals.wav"
        instrumental_path = output_dir / "no_vocals.wav"
        self._write_pcm16_wav(vocals_path, vocals, sample_rate)
        self._write_pcm16_wav(instrumental_path, instrumental, sample_rate)

        return vocals_path if stem == "vocals" else instrumental_path

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

    def _resolve_demucs_segment(self) -> str | None:
        raw_segment = self.settings.demucs_segment.strip()
        if not raw_segment:
            return None

        try:
            segment = float(raw_segment)
        except ValueError as exc:
            raise MediaProcessingError(
                "Invalid DEMUCS_SEGMENT value. It must be a number such as 7.5."
            ) from exc

        if segment <= 0:
            raise MediaProcessingError("Invalid DEMUCS_SEGMENT value. It must be greater than 0.")

        if self._is_transformer_demucs_model() and segment > self.transformer_max_segment:
            segment = self.safe_default_segment

        return f"{segment:g}"

    def _is_transformer_demucs_model(self) -> bool:
        model_name = self.settings.demucs_model.strip().lower()
        return model_name.startswith("htdemucs")

    def _load_pcm_wav(self, source_path: Path) -> tuple["torch.Tensor", int]:
        if np is None or torch is None:
            raise MediaProcessingError("NumPy and PyTorch are required to read normalized WAV files.")

        try:
            with wave.open(str(source_path), "rb") as wav_file:
                channels = wav_file.getnchannels()
                sample_rate = wav_file.getframerate()
                sample_width = wav_file.getsampwidth()
                frame_count = wav_file.getnframes()
                pcm_bytes = wav_file.readframes(frame_count)
        except wave.Error as exc:
            raise MediaProcessingError(f"Failed to read normalized WAV file: {exc}") from exc

        if channels <= 0:
            raise MediaProcessingError("Normalized WAV file does not contain valid audio channels.")
        if sample_width != 2:
            raise MediaProcessingError(
                f"Unsupported normalized WAV sample width: {sample_width * 8} bits. Expected 16-bit PCM."
            )

        pcm = np.frombuffer(pcm_bytes, dtype=np.int16)
        if pcm.size == 0:
            raise MediaProcessingError("Normalized WAV file is empty.")

        wav_tensor = torch.from_numpy(pcm.astype(np.float32) / 32768.0)
        wav_tensor = wav_tensor.view(-1, channels).transpose(0, 1).contiguous()
        return wav_tensor, sample_rate

    def _write_pcm16_wav(self, output_path: Path, wav_tensor: "torch.Tensor", sample_rate: int) -> None:
        if torch is None:
            raise MediaProcessingError("PyTorch is required to write Demucs WAV outputs.")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        clipped = wav_tensor.detach().cpu().float()
        peak = float(clipped.abs().max())
        if peak > 1:
            clipped = clipped / max(1.01 * peak, 1.0)

        pcm_tensor = (clipped.clamp(-1, 1) * 32767.0).round().short()
        interleaved = pcm_tensor.transpose(0, 1).contiguous().numpy()

        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(int(pcm_tensor.shape[0]))
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(interleaved.tobytes())

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
