from __future__ import annotations

import os
import shutil
import subprocess
import wave
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.config import Settings

try:
    import numpy as np
    import torch
except Exception:  # pragma: no cover - torch import errors depend on runtime environment
    np = None
    torch = None

if TYPE_CHECKING:
    from torch import Tensor as TorchTensor
else:  # pragma: no cover - type-only alias
    TorchTensor = Any


class MediaProcessingError(RuntimeError):
    """媒体处理错误"""
    pass


class MediaProcessor:
    """媒体处理器类，负责音频/视频的各种处理操作"""
    transformer_max_segment = 7.8  # Transformer 模型最大分段大小
    safe_default_segment = 7.5  # 安全的默认分段大小
    allowed_extensions = {  # 允许的文件扩展名
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
        """验证文件扩展名是否支持"""
        suffix = Path(filename).suffix.lower()
        if suffix not in self.allowed_extensions:
            allowed = ", ".join(sorted(self.allowed_extensions))
            raise MediaProcessingError(f"Unsupported file type. Allowed extensions: {allowed}")

    def normalize_audio(self, source_path: Path, working_dir: Path) -> Path:
        """标准化音频：转换为双声道 44.1kHz 16-bit PCM WAV 格式"""
        normalized_path = working_dir / "normalized.wav"
        self._run_command(
            [
                self.settings.ffmpeg_bin,
                "-y",
                "-i",
                str(source_path),
                "-vn",  # 不处理视频流
                "-ac",
                "2",  # 双声道
                "-ar",
                "44100",  # 采样率 44.1kHz
                "-c:a",
                "pcm_s16le",  # 16-bit PCM 编码
                str(normalized_path),
            ],
            "Audio normalization failed",
        )
        return normalized_path

    def extract_audio_from_video(self, source_path: Path, output_path: Path) -> None:
        """从视频文件中提取音频并转换为 MP3 格式"""
        self._run_command(
            [
                self.settings.ffmpeg_bin,
                "-y",
                "-i",
                str(source_path),
                "-vn",  # 不处理视频流
                "-acodec",
                "libmp3lame",  # 使用 MP3 编码器
                "-q:a",
                "2",  # 音质等级（0-9，2 为高质量）
                str(output_path),
            ],
            "Audio extraction from video failed",
        )

    def denoise_audio(self, source_path: Path, output_path: Path) -> None:
        """使用 FFmpeg 的 afftdn 滤镜对音频进行降噪处理"""
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
        """使用 Demucs 模型分离音频轨道（人声或伴奏）"""
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

        # 解析设备和分段参数
        device = self._resolve_demucs_device()
        segment = self._resolve_demucs_segment()
        segment_value = float(segment) if segment is not None else None

        try:
            model = get_model(name=self.settings.demucs_model)  # 加载 Demucs 模型
        except Exception as exc:
            raise MediaProcessingError(f"Failed to load Demucs model '{self.settings.demucs_model}': {exc}") from exc

        # 确定模型允许的最大分段大小
        max_allowed_segment = float("inf")
        if isinstance(model, HTDemucs):
            max_allowed_segment = float(model.segment)
        elif isinstance(model, BagOfModels):
            max_allowed_segment = model.max_allowed_segment

        if segment_value is not None and segment_value > max_allowed_segment:
            segment_value = min(self.safe_default_segment, max_allowed_segment)

        wav_tensor, sample_rate = self._load_pcm_wav(source_path)  # 加载 WAV 文件为张量
        if sample_rate != int(getattr(model, "samplerate", sample_rate)):
            raise MediaProcessingError(
                f"Unexpected sample rate for Demucs input: {sample_rate}. "
                f"Expected {getattr(model, 'samplerate', sample_rate)}."
            )

        # 标准化音频数据
        ref = wav_tensor.mean(0)
        mean = ref.mean()
        std = ref.std()
        if float(std) <= 1e-8:
            raise MediaProcessingError("Input audio appears silent after normalization and cannot be separated.")

        normalized = (wav_tensor - mean) / std

        # 使用 Demucs 模型进行音轨分离
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

        # 反标准化
        sources = sources * std + mean
        source_names = list(getattr(model, "sources", []))
        if "vocals" not in source_names:
            raise MediaProcessingError("The selected Demucs model does not expose a vocals stem.")

        # 提取人声和伴奏
        vocals_index = source_names.index("vocals")
        vocals = sources[vocals_index]
        instrumental = torch.zeros_like(vocals)
        for index, name in enumerate(source_names):
            if name != "vocals":
                instrumental += sources[index]

        # 保存分离后的音轨
        output_dir.mkdir(parents=True, exist_ok=True)
        vocals_path = output_dir / "vocals.wav"
        instrumental_path = output_dir / "no_vocals.wav"
        self._write_pcm16_wav(vocals_path, vocals, sample_rate)
        self._write_pcm16_wav(instrumental_path, instrumental, sample_rate)

        return vocals_path if stem == "vocals" else instrumental_path

    def copy_to_output(self, source_path: Path, output_path: Path) -> None:
        """复制文件到输出路径"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, output_path)

    def _run_command(self, command: list[str], title: str) -> None:
        """运行外部命令（如 FFmpeg）并处理错误"""
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
        """构建命令执行环境，确保 FFmpeg 在 PATH 中"""
        env = os.environ.copy()
        ffmpeg_bin = self.settings.ffmpeg_bin.strip()
        ffmpeg_path = Path(ffmpeg_bin)

        if ffmpeg_path.suffix.lower() == ".exe" and ffmpeg_path.parent.exists():
            current_path = env.get("PATH", "")
            env["PATH"] = str(ffmpeg_path.parent) if not current_path else f"{ffmpeg_path.parent}{os.pathsep}{current_path}"

        return env

    def _resolve_demucs_device(self) -> str:
        """解析 Demucs 运行设备（auto/cpu/cuda）"""
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
        """解析 Demucs 分段大小参数"""
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
        """判断是否为 Transformer 类型的 Demucs 模型"""
        model_name = self.settings.demucs_model.strip().lower()
        return model_name.startswith("htdemucs")

    def _load_pcm_wav(self, source_path: Path) -> tuple[TorchTensor, int]:
        """加载 PCM WAV 文件并转换为 PyTorch 张量"""
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

        # 转换为浮点张量并重塑为 (channels, samples) 格式
        wav_tensor = torch.from_numpy(pcm.astype(np.float32) / 32768.0)
        wav_tensor = wav_tensor.view(-1, channels).transpose(0, 1).contiguous()
        return wav_tensor, sample_rate

    def _write_pcm16_wav(self, output_path: Path, wav_tensor: TorchTensor, sample_rate: int) -> None:
        """将 PyTorch 张量写入 16-bit PCM WAV 文件"""
        if torch is None:
            raise MediaProcessingError("PyTorch is required to write Demucs WAV outputs.")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 限制峰值防止削波
        clipped = wav_tensor.detach().cpu().float()
        peak = float(clipped.abs().max())
        if peak > 1:
            clipped = clipped / max(1.01 * peak, 1.0)

        # 转换为 16-bit PCM
        pcm_tensor = (clipped.clamp(-1, 1) * 32767.0).round().short()
        interleaved = pcm_tensor.transpose(0, 1).contiguous().numpy()

        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(int(pcm_tensor.shape[0]))
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(interleaved.tobytes())

    def _detect_cuda_runtime(self) -> tuple[bool, str]:
        """检测 CUDA 运行时是否可用"""
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
        """简化错误信息，提供更友好的提示"""
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
