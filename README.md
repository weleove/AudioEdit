# AudioEdit

一个前后端分离的音频编辑网站基础版，支持以下四类能力：

1. 音乐伴奏提取
2. 音乐人声提取
3. 音频降噪
4. 视频音频提取

项目采用：

- 前端：React + Vite + TypeScript
- 后端：FastAPI + Python
- 音频处理：FFmpeg + Demucs

## 项目结构

```text
AudioEdit/
├─ backend/
│  ├─ app/
│  │  ├─ api/
│  │  ├─ models/
│  │  ├─ schemas/
│  │  ├─ services/
│  │  ├─ config.py
│  │  └─ main.py
│  ├─ pyproject.toml
│  └─ storage/
└─ frontend/
   ├─ src/
   ├─ index.html
   ├─ package.json
   └─ vite.config.ts
```

## 后端依赖安装

建议后端使用 Python 3.11，主要是为了让 `demucs` 和 `torch` 的兼容性更稳。
当前项目默认会通过 `uv` 安装带 CUDA 的 PyTorch 依赖，用于 NVIDIA 显卡加速音轨分离。

### 1. 进入后端目录

```powershell
cd backend
```

### 2. 创建虚拟环境并安装依赖

```powershell
uv venv --python 3.11
.\.venv\Scripts\activate
uv sync
```

说明：

- 首次执行 `uv sync` 会下载较大的 `torch / torchvision / torchaudio` GPU 依赖，耗时会比普通 Python 项目更长。
- 如果你使用的是 NVIDIA RTX 50 系显卡，建议先更新到较新的显卡驱动，再执行 `uv sync`。

### 3. 安装 FFmpeg

推荐在 Windows 上手动安装 FFmpeg，步骤如下：

1. 打开 FFmpeg Windows 构建发布页：
   `https://www.gyan.dev/ffmpeg/builds/`
2. 下载 `ffmpeg-release-full.7z` 或 `ffmpeg-release-full.zip`。
3. 解压到一个固定目录，例如：
   `C:\ffmpeg`
4. 确认以下文件存在：
   - `C:\ffmpeg\bin\ffmpeg.exe`
   - `C:\ffmpeg\bin\ffprobe.exe`
5. 将 `C:\ffmpeg\bin` 加入系统 `PATH`。
6. 重新打开终端，再执行下面的检查命令。

如果你不想修改系统 `PATH`，也可以仅在启动后端前单独指定：

```powershell
$env:FFMPEG_BIN = "C:\ffmpeg\bin\ffmpeg.exe"
```

安装后确认：

```powershell
ffmpeg -version
```

如果上面的命令找不到，也可以直接执行：

```powershell
C:\ffmpeg\bin\ffmpeg.exe -version
```

### 4. 启动后端

```powershell
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端默认地址：

```text
http://localhost:8000
```

## 前端依赖安装

### 1. 进入前端目录

```powershell
cd frontend
```

### 2. 安装依赖

```powershell
npm install
```

### 3. 启动前端

```powershell
npm run dev
```

前端默认地址：

```text
http://localhost:5173
```

## 环境变量

后端可选环境变量：

```text
FRONTEND_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
MAX_UPLOAD_SIZE_MB=500
DEMUCS_MODEL=htdemucs
DEMUCS_DEVICE=cuda
DEMUCS_SEGMENT=7
DEMUCS_JOBS=0
FFMPEG_BIN=ffmpeg
```

说明：

- `DEMUCS_DEVICE`：可选 `cuda`、`cpu`、`auto`。有 NVIDIA 显卡时建议使用 `cuda`。
- `DEMUCS_SEGMENT`：控制 Demucs 分块时长。`htdemucs` 这类 Transformer 模型不建议超过 `7.8`，默认 `7` 更稳，记得取整数。
- `DEMUCS_JOBS`：CPU 并行 worker 数。显存或内存紧张时建议保持 `0`。
- `FFMPEG_BIN`：如果 `ffmpeg.exe` 不在 `PATH` 中，可以直接写绝对路径，例如 `C:\ffmpeg\bin\ffmpeg.exe`。

前端可选环境变量：

```text
VITE_API_BASE_URL=http://localhost:8000
```

## GPU 加速说明

项目中的伴奏提取和人声提取默认使用 Demucs。
只要后端环境中的 PyTorch 能识别 CUDA，并且 `DEMUCS_DEVICE=cuda`，就会优先走 GPU。

建议在后端虚拟环境中执行以下命令检查：

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.version.cuda); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no gpu')"
```

如果输出中：

- `torch.cuda.is_available()` 为 `True`，说明后端可以使用 GPU。
- `torch.cuda.is_available()` 为 `False`，说明当前环境会退回 CPU。

## 常见问题

### 1. 伴奏提取或人声提取为什么没有用 GPU？

常见原因：

- 当前虚拟环境安装的是 CPU 版 PyTorch。
- 显卡驱动过旧。
- `DEMUCS_DEVICE` 被设置成了 `cpu`。

建议先执行上面的 CUDA 检查命令确认。

### 2. 出现 `Cannot use a Transformer model with a longer segment than it was trained for`

这是 `DEMUCS_SEGMENT` 设置过大导致的。
对于默认的 `htdemucs` 模型，建议使用：

```powershell
$env:DEMUCS_SEGMENT = "7"
```

如果显存紧张或者系统容易卡顿，也可以进一步降低到 `6` 或 `5`。

### 3. 处理时电脑黑屏、卡死或自动重启

这通常不是前端问题，而是高负载下的系统稳定性问题。建议优先检查：

- 是否存在 CPU / GPU 超频、降压或内存超频。
- 电源和散热是否稳定。
- 是否同时提交了多个大文件任务。

如果需要先以更稳为主运行，可以尝试：

```powershell
$env:DEMUCS_DEVICE = "cuda"
$env:DEMUCS_SEGMENT = "5"
$env:DEMUCS_JOBS = "0"
```

### 4. FFmpeg 明明装了，但后端仍提示找不到

请确认：

- `ffmpeg.exe` 的实际路径正确。
- 修改 `PATH` 后已经重新打开终端。
- 启动后端前已正确设置 `FFMPEG_BIN`。

例如：

```powershell
$env:FFMPEG_BIN = "C:\ffmpeg\bin\ffmpeg.exe"
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 已实现能力说明

### 1. 音乐伴奏提取

后端通过 `Demucs` 进行双声部拆分，返回 `no_vocals.wav` 作为伴奏结果。

### 2. 音乐人声提取

后端通过 `Demucs` 进行双声部拆分，返回 `vocals.wav`。

### 3. 音频降噪

后端使用 `ffmpeg` 的 `afftdn` 滤镜进行基础降噪。

### 4. 视频音频提取

后端使用 `ffmpeg` 从视频中提取音轨，并导出为 `mp3`。

## API 简要说明

### 健康检查

```http
GET /api/health
```

### 创建任务

```http
POST /api/jobs
Content-Type: multipart/form-data
```

表单字段：

- `operation`
- `file`

可选操作值：

- `extract_instrumental`
- `extract_vocals`
- `denoise_audio`
- `extract_audio_from_video`

### 查询任务

```http
GET /api/jobs
GET /api/jobs/{job_id}
GET /api/jobs/{job_id}/download
```

## 后续可扩展方向

1. 引入 Redis + Celery / Dramatiq 作为正式任务队列
2. 增加波形预览和音频试听
3. 增加处理参数，比如降噪强度、导出格式、采样率
4. 接入对象存储，支持大文件和历史任务管理
