import { FormEvent, useEffect, useState } from "react";

import { OutputAudioPreview, SelectedFileWaveformPreview } from "./AudioPreview";
import { createJob, downloadJobResult, getJobs } from "./api";
import type { JobResponse, JobStatus, OperationType } from "./types";

type Language = "en" | "zh";

interface OperationContent {
  title: string;
  subtitle: string;
  detail: string;
}

interface Copy {
  htmlLang: string;
  locale: string;
  pageTitle: string;
  brand: string;
  languageLabel: string;
  heroTitle: string;
  heroDescription: string;
  metrics: {
    workflows: string;
    backend: string;
    frontend: string;
  };
  operations: Record<OperationType, OperationContent>;
  statuses: Record<JobStatus, string>;
  createJobTitle: string;
  currentModeLabel: string;
  chooseFileLabel: string;
  supportedFiles: string;
  noFileSelected: string;
  selectFileError: string;
  submitting: string;
  startAction: string;
  queueTitle: string;
  queueDescription: string;
  emptyTitle: string;
  emptyDescription: string;
  createdAtLabel: string;
  updatedAtLabel: string;
  downloadResult: string;
  savingResult: string;
  inputWaveformTitle: string;
  outputWaveformTitle: string;
  outputAudioTitle: string;
  previewLoading: string;
  previewUnavailable: string;
  durationLabel: string;
  previewFailed: string;
}

interface SaveFilePickerType {
  description?: string;
  accept: Record<string, string[]>;
}

type SaveFilePickerWindow = Window & {
  showSaveFilePicker?: (options?: {
    suggestedName?: string;
    excludeAcceptAllOption?: boolean;
    types?: SaveFilePickerType[];
  }) => Promise<{
    createWritable: () => Promise<{
      write: (data: Blob) => Promise<void>;
      close: () => Promise<void>;
    }>;
  }>;
};

const OPERATION_ORDER: OperationType[] = [
  "extract_instrumental",
  "extract_vocals",
  "denoise_audio",
  "extract_audio_from_video",
];

const ACCEPT_BY_OPERATION: Record<OperationType, string> = {
  extract_instrumental: "audio/*,video/*",
  extract_vocals: "audio/*,video/*",
  denoise_audio: "audio/*,video/*",
  extract_audio_from_video: "video/*",
};

const COPY_BY_LANGUAGE: Record<Language, Copy> = {
  en: {
    htmlLang: "en",
    locale: "en-US",
    pageTitle: "AudioEdit Studio",
    brand: "AudioEdit Studio",
    languageLabel: "Language",
    heroTitle: "A focused online workspace for modern audio editing flows.",
    heroDescription:
      "The frontend is built with React and the backend is built with FastAPI. Upload audio or video, trigger processing jobs, monitor task status, and download finished media from one clean dashboard.",
    metrics: {
      workflows: "processing workflows",
      backend: "async backend endpoints",
      frontend: "separate frontend client",
    },
    operations: {
      extract_instrumental: {
        title: "Instrumental Split",
        subtitle: "Return the backing track",
        detail: "Use Demucs to remove vocals and export a clean no-vocals track.",
      },
      extract_vocals: {
        title: "Vocal Split",
        subtitle: "Return the vocal stem",
        detail: "Use Demucs to isolate vocals for remixing, practice, or analysis.",
      },
      denoise_audio: {
        title: "Noise Reduction",
        subtitle: "Clean light background noise",
        detail: "Run an FFmpeg denoise filter to reduce hiss and ambient noise.",
      },
      extract_audio_from_video: {
        title: "Audio From Video",
        subtitle: "Export the video soundtrack",
        detail: "Extract the audio stream from a video file and export it as MP3.",
      },
    },
    statuses: {
      queued: "Queued",
      processing: "Processing",
      completed: "Completed",
      failed: "Failed",
    },
    createJobTitle: "Create a new job",
    currentModeLabel: "Current mode",
    chooseFileLabel: "Choose a file",
    supportedFiles: "Supported: common audio files and mainstream video formats",
    noFileSelected: "No file selected yet",
    selectFileError: "Please select a file first.",
    submitting: "Submitting...",
    startAction: "Start",
    queueTitle: "Job queue",
    queueDescription: "Running jobs are refreshed automatically.",
    emptyTitle: "No jobs yet.",
    emptyDescription: "Your uploaded tasks will appear here with status and download actions.",
    createdAtLabel: "Created",
    updatedAtLabel: "Updated",
    downloadResult: "Download result",
    savingResult: "Saving...",
    inputWaveformTitle: "Input waveform",
    outputWaveformTitle: "Output waveform",
    outputAudioTitle: "Result audio preview",
    previewLoading: "Generating preview...",
    previewUnavailable: "Preview is unavailable for this media in the current browser.",
    durationLabel: "Duration",
    previewFailed: "Failed to generate the media preview.",
  },
  zh: {
    htmlLang: "zh-CN",
    locale: "zh-CN",
    pageTitle: "AudioEdit 音频编辑工作台",
    brand: "AudioEdit Studio",
    languageLabel: "语言",
    heroTitle: "一个用于音频编辑的在线工作台。",
    heroDescription:
      "你可以上传音频或视频，发起处理任务，查看任务状态，并在同一面板中下载处理结果。",
    metrics: {
      workflows: "个处理流程",
      backend: "异步后端接口",
      frontend: "独立前端客户端",
    },
    operations: {
      extract_instrumental: {
        title: "伴奏提取",
        subtitle: "输出无人声伴奏",
        detail: "使用 Demucs 去除人声，导出干净的无主唱伴奏轨。",
      },
      extract_vocals: {
        title: "人声提取",
        subtitle: "输出独立人声轨",
        detail: "使用 Demucs 分离人声，适合混音、练习或分析。",
      },
      denoise_audio: {
        title: "音频降噪",
        subtitle: "清理轻度背景噪声",
        detail: "使用 FFmpeg 降噪滤镜降低底噪和环境杂音。",
      },
      extract_audio_from_video: {
        title: "视频提音",
        subtitle: "导出视频音轨",
        detail: "从视频文件中提取音频流并导出为 MP3。",
      },
    },
    statuses: {
      queued: "排队中",
      processing: "处理中",
      completed: "已完成",
      failed: "失败",
    },
    createJobTitle: "新建任务",
    currentModeLabel: "当前模式",
    chooseFileLabel: "选择文件",
    supportedFiles: "支持常见音频文件和主流视频格式",
    noFileSelected: "尚未选择文件",
    selectFileError: "请先选择一个文件。",
    submitting: "提交中...",
    startAction: "开始",
    queueTitle: "任务队列",
    queueDescription: "运行中的任务会自动刷新。",
    emptyTitle: "还没有任务。",
    emptyDescription: "你上传的任务会显示在这里，并附带状态和下载入口。",
    createdAtLabel: "创建时间",
    updatedAtLabel: "更新时间",
    downloadResult: "下载结果",
    savingResult: "保存中...",
    inputWaveformTitle: "\u8f93\u5165\u6ce2\u5f62",
    outputWaveformTitle: "\u8f93\u51fa\u6ce2\u5f62",
    outputAudioTitle: "\u8f93\u51fa\u97f3\u9891\u8bd5\u542c",
    previewLoading: "\u6b63\u5728\u751f\u6210\u9884\u89c8...",
    previewUnavailable: "\u5f53\u524d\u6d4f\u89c8\u5668\u6682\u65f6\u65e0\u6cd5\u751f\u6210\u8be5\u5a92\u4f53\u7684\u9884\u89c8\u3002",
    durationLabel: "\u65f6\u957f",
    previewFailed: "\u5a92\u4f53\u9884\u89c8\u751f\u6210\u5931\u8d25\u3002",
  },
};

const EXACT_ZH_TEXT: Record<string, string> = {
  "Job created and waiting to start.": "任务已创建，等待开始处理。",
  "Processing started. Please wait.": "任务已开始处理，请稍候。",
  "Processing completed. Result file is ready for download.": "处理完成，结果文件已可下载。",
  "Processing failed.": "处理失败。",
  "Uploaded file exceeds the size limit.": "上传文件超过大小限制。",
  "Unknown operation type.": "未知的处理类型。",
  "Job not found.": "任务不存在。",
  "Result file is not ready yet.": "结果文件尚未生成。",
  "Result file does not exist.": "结果文件不存在。",
  "Request failed.": "请求失败。",
  "Failed to load jobs.": "加载任务失败。",
  "Failed to create the job.": "创建任务失败。",
  "Please select a file first.": "请先选择一个文件。",
  "Failed to fetch": "网络请求失败。",
  "No extra error output was returned.": "没有返回更多错误信息。",
};

const PREFIX_ZH_TEXT: Array<[string, string]> = [
  ["Unsupported file type. Allowed extensions:", "不支持该文件类型，允许的扩展名："],
  ["Audio normalization failed:", "音频标准化失败："],
  ["Audio extraction from video failed:", "视频提取音频失败："],
  ["Noise reduction failed:", "音频降噪失败："],
  ["Stem separation failed:", "音轨分离失败："],
  ["Expected output file was not found:", "未找到预期输出文件："],
];

function getInitialLanguage(): Language {
  if (typeof window === "undefined") {
    return "en";
  }

  const savedLanguage = window.localStorage.getItem("audioedit-language");
  if (savedLanguage === "en" || savedLanguage === "zh") {
    return savedLanguage;
  }

  return window.navigator.language.toLowerCase().startsWith("zh") ? "zh" : "en";
}

function localizeRuntimeText(language: Language, text: string | null | undefined): string {
  if (!text || language === "en") {
    return text ?? "";
  }

  const exactMatch = EXACT_ZH_TEXT[text];
  if (exactMatch) {
    return exactMatch;
  }

  for (const [prefix, translatedPrefix] of PREFIX_ZH_TEXT) {
    if (text.startsWith(prefix)) {
      return `${translatedPrefix}${text.slice(prefix.length)}`;
    }
  }

  return text;
}

function formatTime(value: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

function formatStartLabel(language: Language, action: string, title: string): string {
  return language === "zh" ? `${action}${title}` : `${action} ${title}`;
}

function getFilenameExtension(filename: string): string | null {
  const parts = filename.split(".");
  if (parts.length < 2) {
    return null;
  }

  const extension = parts[parts.length - 1]?.trim().toLowerCase();
  return extension ? `.${extension}` : null;
}

function buildPickerTypes(suggestedName: string, mimeType: string): SaveFilePickerType[] | undefined {
  const extension = getFilenameExtension(suggestedName);
  if (!extension || !mimeType) {
    return undefined;
  }

  return [
    {
      description: `${extension.slice(1).toUpperCase()} media`,
      accept: {
        [mimeType]: [extension],
      },
    },
  ];
}

export default function App() {
  const [language, setLanguage] = useState<Language>(() => getInitialLanguage());
  const [selectedOperation, setSelectedOperation] = useState<OperationType>("extract_instrumental");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [jobs, setJobs] = useState<JobResponse[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [downloadingJobId, setDownloadingJobId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const copy = COPY_BY_LANGUAGE[language];
  const operations = OPERATION_ORDER.map((operationId) => ({
    id: operationId,
    accept: ACCEPT_BY_OPERATION[operationId],
    ...copy.operations[operationId],
  }));
  const currentOperation = operations.find((item) => item.id === selectedOperation) ?? operations[0];
  const hasRunningJob = jobs.some((job) => job.status === "queued" || job.status === "processing");

  useEffect(() => {
    window.localStorage.setItem("audioedit-language", language);
    document.documentElement.lang = copy.htmlLang;
    document.title = copy.pageTitle;
  }, [copy.htmlLang, copy.pageTitle, language]);

  async function loadJobs() {
    try {
      const nextJobs = await getJobs();
      setJobs(nextJobs);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to load jobs.";
      setErrorMessage(message);
    }
  }

  useEffect(() => {
    void loadJobs();
  }, []);

  useEffect(() => {
    if (!hasRunningJob) {
      return;
    }

    const timer = window.setInterval(() => {
      void loadJobs();
    }, 3000);

    return () => {
      window.clearInterval(timer);
    };
  }, [hasRunningJob]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!selectedFile) {
      setErrorMessage(copy.selectFileError);
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      await createJob(selectedFile, selectedOperation);
      setSelectedFile(null);
      await loadJobs();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to create the job.";
      setErrorMessage(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function saveBlobToLocalFile(blob: Blob, suggestedName: string) {
    const pickerWindow = window as SaveFilePickerWindow;

    if (typeof pickerWindow.showSaveFilePicker === "function") {
      const handle = await pickerWindow.showSaveFilePicker({
        suggestedName,
        types: buildPickerTypes(suggestedName, blob.type),
      });
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      return;
    }

    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = suggestedName;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  }

  async function handleDownload(job: JobResponse) {
    if (!job.download_url) {
      return;
    }

    setDownloadingJobId(job.job_id);
    setErrorMessage(null);

    try {
      const { blob, filename } = await downloadJobResult(job.download_url);
      await saveBlobToLocalFile(blob, filename);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        return;
      }
      const message = error instanceof Error ? error.message : "Request failed.";
      setErrorMessage(message);
    } finally {
      setDownloadingJobId(null);
    }
  }

  return (
    <div className="page-shell">
      <div className="page-glow page-glow-left" />
      <div className="page-glow page-glow-right" />

      <main className="app-layout">
        <section className="hero">
          <div className="hero-copy">
            <div className="hero-toolbar">
              <span className="eyebrow">{copy.brand}</span>

              <div className="language-switch">
                <span className="language-caption">{copy.languageLabel}</span>
                <div className="language-actions" role="group" aria-label={copy.languageLabel}>
                  <button
                    type="button"
                    className={language === "en" ? "language-button active" : "language-button"}
                    onClick={() => setLanguage("en")}
                  >
                    EN
                  </button>
                  <button
                    type="button"
                    className={language === "zh" ? "language-button active" : "language-button"}
                    onClick={() => setLanguage("zh")}
                  >
                    中文
                  </button>
                </div>
              </div>
            </div>

            <h1>{copy.heroTitle}</h1>
            <p>{copy.heroDescription}</p>
          </div>
        </section>

        <section className="operation-grid">
          {operations.map((item) => (
            <button
              key={item.id}
              type="button"
              className={item.id === selectedOperation ? "operation-card active" : "operation-card"}
              onClick={() => {
                setSelectedOperation(item.id);
                setErrorMessage(null);
              }}
            >
              <div className="operation-header">
                <h2>{item.title}</h2>
                <span>{item.subtitle}</span>
              </div>
              <p>{item.detail}</p>
            </button>
          ))}
        </section>

        <section className="workspace-grid">
          <form className="panel upload-panel" onSubmit={handleSubmit}>
            <div className="panel-header">
              <h3>{copy.createJobTitle}</h3>
              <p>
                {copy.currentModeLabel}: {currentOperation.title}
              </p>
            </div>

            <label className="field-label" htmlFor="media-file">
              {copy.chooseFileLabel}
            </label>
            <input
              id="media-file"
              className="file-input"
              type="file"
              accept={currentOperation.accept}
              onChange={(event) => {
                const nextFile = event.target.files?.[0] ?? null;
                setSelectedFile(nextFile);
              }}
            />

            <div className="file-hint">
              <span>{copy.supportedFiles}</span>
              <strong>{selectedFile ? selectedFile.name : copy.noFileSelected}</strong>
            </div>

            <SelectedFileWaveformPreview file={selectedFile} copy={copy} />

            {errorMessage ? <div className="error-box">{localizeRuntimeText(language, errorMessage)}</div> : null}

            <button className="submit-button" type="submit" disabled={isSubmitting}>
              {isSubmitting ? copy.submitting : formatStartLabel(language, copy.startAction, currentOperation.title)}
            </button>
          </form>

          <section className="panel queue-panel">
            <div className="panel-header">
              <h3>{copy.queueTitle}</h3>
              <p>{copy.queueDescription}</p>
            </div>

            {jobs.length === 0 ? (
              <div className="empty-state">
                <p>{copy.emptyTitle}</p>
                <span>{copy.emptyDescription}</span>
              </div>
            ) : (
              <div className="job-list">
                {jobs.map((job) => (
                  <article key={job.job_id} className="job-card">
                    <div className="job-card-top">
                      <div>
                        <strong>{copy.operations[job.operation].title}</strong>
                        <span>{job.original_filename}</span>
                      </div>
                      <span className={`status-badge status-${job.status}`}>{copy.statuses[job.status]}</span>
                    </div>

                    <p className="job-message">{localizeRuntimeText(language, job.message)}</p>

                    <div className="job-meta">
                      <span>
                        {copy.createdAtLabel}: {formatTime(job.created_at, copy.locale)}
                      </span>
                      <span>
                        {copy.updatedAtLabel}: {formatTime(job.updated_at, copy.locale)}
                      </span>
                    </div>

                    {job.error ? <div className="error-inline">{localizeRuntimeText(language, job.error)}</div> : null}

                    {job.download_url ? <OutputAudioPreview downloadUrl={job.download_url} copy={copy} /> : null}

                    {job.download_url ? (
                      <button
                        type="button"
                        className="download-link"
                        disabled={downloadingJobId === job.job_id}
                        onClick={() => {
                          void handleDownload(job);
                        }}
                      >
                        {downloadingJobId === job.job_id ? copy.savingResult : copy.downloadResult}
                      </button>
                    ) : null}
                  </article>
                ))}
              </div>
            )}
          </section>
        </section>
      </main>
    </div>
  );
}
