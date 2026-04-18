export type OperationType =
  | "extract_instrumental"
  | "extract_vocals"
  | "denoise_audio"
  | "extract_audio_from_video";

export type JobStatus = "queued" | "processing" | "completed" | "failed";

export interface JobCreateResponse {
  job_id: string;
  status: JobStatus;
  message: string;
}

export interface JobResponse {
  job_id: string;
  operation: OperationType;
  original_filename: string;
  status: JobStatus;
  message: string;
  created_at: string;
  updated_at: string;
  error: string | null;
  download_url: string | null;
}

