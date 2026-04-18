import type { JobCreateResponse, JobResponse, OperationType } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API_ROOT = API_BASE_URL.replace(/\/+$/, "");

function joinUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }

  if (path.startsWith("/")) {
    return `${API_ROOT}${path}`;
  }

  return `${API_ROOT}/${path}`;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(joinUrl(path), init);
  const data = (await response.json().catch(() => null)) as { detail?: string } | null;

  if (!response.ok) {
    throw new Error(data?.detail ?? "Request failed.");
  }

  return data as T;
}

function extractFilename(contentDisposition: string | null, fallback = "download.bin"): string {
  if (!contentDisposition) {
    return fallback;
  }

  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }

  const asciiMatch = contentDisposition.match(/filename="([^"]+)"/i) ?? contentDisposition.match(/filename=([^;]+)/i);
  if (asciiMatch?.[1]) {
    return asciiMatch[1].trim();
  }

  return fallback;
}

export async function createJob(file: File, operation: OperationType): Promise<JobCreateResponse> {
  const formData = new FormData();
  formData.append("operation", operation);
  formData.append("file", file);

  return requestJson<JobCreateResponse>("/api/jobs", {
    method: "POST",
    body: formData,
  });
}

export function getJobs(): Promise<JobResponse[]> {
  return requestJson<JobResponse[]>("/api/jobs");
}

export function getJob(jobId: string): Promise<JobResponse> {
  return requestJson<JobResponse>(`/api/jobs/${jobId}`);
}

export async function downloadJobResult(path: string): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(joinUrl(path));

  if (!response.ok) {
    const data = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(data?.detail ?? "Request failed.");
  }

  const blob = await response.blob();
  const filename = extractFilename(response.headers.get("content-disposition"));
  return { blob, filename };
}
