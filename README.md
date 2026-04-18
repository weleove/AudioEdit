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

### 3. 安装 FFmpeg

Windows 上可以直接用：

```powershell
winget install Gyan.FFmpeg
```

安装后确认：

```powershell
ffmpeg -version
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
FFMPEG_BIN=ffmpeg
```

前端可选环境变量：

```text
VITE_API_BASE_URL=http://localhost:8000
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

