# AudioEdit

一个前后端分离的音频编辑项目，当前支持以下四类能力：

1. 音乐伴奏提取
2. 音乐人声提取
3. 音频降噪
4. 视频音频提取

项目采用：

- 前端：React + Vite + TypeScript
- 后端：FastAPI + Python
- 音频处理：FFmpeg + Demucs
- 临时二进制存储：Redis 优先，未配置时回退为进程内临时内存


<p align="center">
  <img src="interface\Intopage.png" width="1200" alt="主页示意图">
</p>

## 项目结构

```text
AudioEdit/
├─ app/
│  ├─ api/
│  ├─ models/
│  ├─ schemas/
│  ├─ services/
│  ├─ config.py
│  └─ main.py
├─ interface/
│  ├─ src/
│  ├─ index.html
│  ├─ package.json
│  └─ vite.config.ts
├─ .venv/
├─ pyproject.toml
├─ uv.lock
└─ README.md
```

说明：

- 当前代码已经不再依赖项目目录下的 `storage/` 作为正式上传和输出目录。
- 音频处理仍然会在系统临时目录中创建短生命周期的工作文件，因为 FFmpeg 和 Demucs 仍然需要文件路径参与处理。
- 如果仓库里还保留旧的 `storage/` 目录，通常只是历史调试产物，不再是当前主流程的必要组成部分。

## 后端依赖安装

建议使用 Python 3.11。
当前项目默认会通过 `uv` 安装带 CUDA 的 PyTorch 依赖，以便在支持的 NVIDIA 显卡上使用 GPU 加速音轨分离。

### 1. 在项目根目录创建虚拟环境并安装依赖

```powershell
uv venv --python 3.11
.\.venv\Scripts\activate
uv sync
```

说明：

- 首次执行 `uv sync` 会下载较大的 `torch / torchvision / torchaudio` GPU 依赖，耗时会明显长于普通 Python 项目。
- 如果你使用的是 NVIDIA RTX 50 系显卡，建议先更新显卡驱动，再执行 `uv sync`。
- 如果你准备启用 Redis 暂存，请确保 `uv sync` 之后已经安装了 `redis` Python 包。

### 2. 手动安装 FFmpeg

推荐在 Windows 上手动安装 FFmpeg，步骤如下：

1. 打开 FFmpeg Windows 构建发布页：
   `https://www.gyan.dev/ffmpeg/builds/`
2. 下载 `ffmpeg-release-full.7z` 或 `ffmpeg-release-full.zip`。
3. 解压到固定目录，例如：
   `C:\ffmpeg`
4. 确认以下文件存在：
   - `C:\ffmpeg\bin\ffmpeg.exe`
   - `C:\ffmpeg\bin\ffprobe.exe`
5. 将 `C:\ffmpeg\bin` 加入系统 `PATH`。
6. 重新打开终端后执行检查命令。

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

### 3. 准备 Redis

当前版本会优先把上传文件和处理结果暂存到 Redis。
如果没有配置 `REDIS_URL`，系统会退回到进程内临时内存存储：

- 优点：无需额外依赖，适合本地快速开发
- 限制：程序重启后临时文件和结果会丢失

建议开发或部署时显式启用 Redis。

最简单的本地启动方式之一是使用 Docker：

```powershell
docker run --name audioedit-redis -p 6379:6379 -d redis:7
```

如果你已经在本机安装了 Redis，也可以直接启动本地服务。

### 4. 启动后端

在项目根目录执行：

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
cd interface
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
REDIS_URL=redis://127.0.0.1:6379/0
BINARY_KEY_PREFIX=audioedit
BINARY_TTL_SECONDS=3600
TEMP_WORK_DIR=C:\Users\<你的用户名>\AppData\Local\Temp\audioedit
```

说明：

- `DEMUCS_DEVICE`：可选 `cuda`、`cpu`、`auto`。有 NVIDIA 显卡时建议使用 `cuda`。
- `DEMUCS_SEGMENT`：控制 Demucs 分块时长。默认模型 `htdemucs` 建议不要超过 `7.8`，默认 `7` 更稳。
- `DEMUCS_JOBS`：CPU 并行 worker 数。显存或内存紧张时建议保持 `0`。
- `FFMPEG_BIN`：如果 `ffmpeg.exe` 不在 `PATH` 中，可以直接写绝对路径。
- `REDIS_URL`：配置后，上传文件和结果文件会优先存入 Redis。
- `BINARY_KEY_PREFIX`：Redis key 前缀，便于与其他项目隔离。
- `BINARY_TTL_SECONDS`：Redis 中临时文件和结果的保留秒数。超过该时间后，结果可能失效。
- `TEMP_WORK_DIR`：系统临时工作目录，FFmpeg 和 Demucs 的处理过程会在这里创建短生命周期文件。

前端可选环境变量：

```text
VITE_API_BASE_URL=http://localhost:8000
```

## 文件存储说明

当前版本的文件流转方式如下：

1. 用户上传文件
2. 后端优先把原始二进制写入 Redis
3. 任务开始处理时，后端把输入文件写入系统临时目录
4. FFmpeg / Demucs 在临时目录完成处理
5. 处理结果重新写回 Redis
6. 用户在前端点击下载后，将结果保存到本地

这意味着：

- 项目目录下不再长期堆积上传文件和输出文件
- Redis 更适合做短期暂存，不适合作为长期大文件仓库
- 如果你计划长期保存结果，建议后续接入对象存储或数据库元数据管理

## 下载与本地保存说明

前端下载按钮现在会优先尝试调用浏览器的保存文件选择器。
如果当前浏览器支持 `showSaveFilePicker`，用户可以直接选择本地保存路径。

如果浏览器不支持该能力，则会退回到普通下载行为：

- 文件会按浏览器默认下载策略保存
- 如果浏览器开启了“每次下载前询问保存位置”，用户仍然可以手动选择路径

## GPU 加速说明

项目中的伴奏提取和人声提取默认使用 Demucs。
只要后端环境中的 PyTorch 能识别 CUDA，并且 `DEMUCS_DEVICE=cuda`，就会优先走 GPU。

建议在项目根目录执行以下命令检查：

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.version.cuda); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no gpu')"
```

如果输出中：

- `torch.cuda.is_available()` 为 `True`，说明后端可以使用 GPU
- `torch.cuda.is_available()` 为 `False`，说明当前环境会退回 CPU

## 已实现能力说明

### 1. 音乐伴奏提取

后端通过 `Demucs` 进行双声部拆分，返回 `instrumental.wav`。

### 2. 音乐人声提取

后端通过 `Demucs` 进行双声部拆分，返回 `vocals.wav`。

### 3. 音频降噪

后端使用 `ffmpeg` 的 `afftdn` 滤镜进行基础降噪，返回 `denoised.wav`。

### 4. 视频音频提取

后端使用 `ffmpeg` 从视频中提取音轨，并导出为 `extracted_audio.mp3`。

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

说明：

- `/download` 接口现在直接返回二进制结果，不再依赖项目目录下的持久化输出文件。
- 如果结果在 Redis 或内存暂存中已经过期，下载接口会返回文件不存在。

## 常见问题

### 1. 伴奏提取或人声提取为什么没有用 GPU？

常见原因：

- 当前虚拟环境安装的是 CPU 版 PyTorch
- 显卡驱动过旧
- `DEMUCS_DEVICE` 被设置成了 `cpu`

建议先执行上面的 CUDA 检查命令确认。

### 2. 出现 `Cannot use a Transformer model with a longer segment than it was trained for`

这是 `DEMUCS_SEGMENT` 设置过大导致的。
对于默认的 `htdemucs` 模型，建议：

```powershell
$env:DEMUCS_SEGMENT = "7"
```

如果显存紧张或者系统容易卡顿，也可以进一步降低到 `6` 或 `5`。

### 3. 处理时电脑黑屏、卡死或自动重启

这通常不是前端问题，而是高负载下的系统稳定性问题。建议优先检查：

- 是否存在 CPU / GPU 超频、降压或内存超频
- 电源和散热是否稳定
- 是否同时提交了多个大文件任务

如果需要先以更稳为主运行，可以尝试：

```powershell
$env:DEMUCS_DEVICE = "cuda"
$env:DEMUCS_SEGMENT = "5"
$env:DEMUCS_JOBS = "0"
```

### 4. FFmpeg 明明装了，但后端仍提示找不到

请确认：

- `ffmpeg.exe` 的实际路径正确
- 修改 `PATH` 后已经重新打开终端
- 启动后端前已正确设置 `FFMPEG_BIN`

例如：

```powershell
$env:FFMPEG_BIN = "C:\ffmpeg\bin\ffmpeg.exe"
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. 下载结果时报“文件不存在”

常见原因：

- Redis 中的结果已经超过 `BINARY_TTL_SECONDS`
- 当前使用的是进程内临时内存，服务重启后结果已丢失
- 任务尚未真正完成

如果你希望结果保留更久，可以适当增大：

```powershell
$env:BINARY_TTL_SECONDS = "14400"
```

## 后续可扩展方向

1. 用 Redis 保存任务元数据，而不是只保存临时二进制
2. 引入 Celery / Dramatiq 作为正式任务队列
3. 接入对象存储，替代 Redis 承担大文件暂存与长期保存
4. 增加波形预览、试听和更多处理参数
