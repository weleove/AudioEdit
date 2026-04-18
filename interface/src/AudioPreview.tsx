import { useEffect, useState } from "react";

import { downloadJobResult } from "./api";

interface AudioPreviewCopy {
  inputWaveformTitle: string;
  outputWaveformTitle: string;
  outputAudioTitle: string;
  previewLoading: string;
  previewUnavailable: string;
  previewFailed: string;
  durationLabel: string;
}

interface WaveformData {
  peaks: number[];
  durationSeconds: number;
}

interface OutputWaveformData extends WaveformData {
  audioUrl: string;
}

type InputPreviewState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; data: WaveformData }
  | { status: "error" };

type OutputPreviewState =
  | { status: "loading" }
  | { status: "ready"; data: OutputWaveformData }
  | { status: "error" };

type AudioContextConstructor = new (contextOptions?: AudioContextOptions) => AudioContext;

type AudioContextWindow = Window & {
  webkitAudioContext?: AudioContextConstructor;
};

let sharedAudioContext: AudioContext | null = null;

function getAudioContext(): AudioContext {
  const contextConstructor = window.AudioContext ?? (window as AudioContextWindow).webkitAudioContext;

  if (!contextConstructor) {
    throw new Error("Audio preview is not supported in this browser.");
  }

  sharedAudioContext ??= new contextConstructor();
  return sharedAudioContext;
}

async function decodeAudioBuffer(arrayBuffer: ArrayBuffer): Promise<AudioBuffer> {
  const audioContext = getAudioContext();
  return audioContext.decodeAudioData(arrayBuffer.slice(0));
}

function buildWaveform(audioBuffer: AudioBuffer, bucketCount = 72): number[] {
  const channels = Array.from({ length: audioBuffer.numberOfChannels }, (_, index) => audioBuffer.getChannelData(index));
  const sampleCount = channels[0]?.length ?? 0;
  const bucketSize = Math.max(1, Math.floor(sampleCount / bucketCount));

  return Array.from({ length: bucketCount }, (_, bucketIndex) => {
    const start = bucketIndex * bucketSize;
    const end = bucketIndex === bucketCount - 1 ? sampleCount : Math.min(sampleCount, start + bucketSize);
    let peak = 0;

    for (let sampleIndex = start; sampleIndex < end; sampleIndex += 1) {
      let total = 0;

      for (const channel of channels) {
        total += Math.abs(channel[sampleIndex] ?? 0);
      }

      peak = Math.max(peak, total / Math.max(1, channels.length));
    }

    return Math.max(0.06, Math.min(1, peak));
  });
}

async function buildWaveformFromArrayBuffer(arrayBuffer: ArrayBuffer): Promise<WaveformData> {
  const audioBuffer = await decodeAudioBuffer(arrayBuffer);
  return {
    peaks: buildWaveform(audioBuffer),
    durationSeconds: audioBuffer.duration,
  };
}

function formatDuration(durationSeconds: number): string {
  if (!Number.isFinite(durationSeconds) || durationSeconds <= 0) {
    return "00:00";
  }

  const totalSeconds = Math.round(durationSeconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return [hours, minutes, seconds].map((value) => String(value).padStart(2, "0")).join(":");
  }

  return [minutes, seconds].map((value) => String(value).padStart(2, "0")).join(":");
}

function WaveformBlock({
  title,
  durationLabel,
  data,
}: {
  title: string;
  durationLabel: string;
  data: WaveformData;
}) {
  return (
    <section className="preview-card">
      <div className="preview-header">
        <strong>{title}</strong>
        <span>
          {durationLabel}: {formatDuration(data.durationSeconds)}
        </span>
      </div>

      <div className="waveform-bars" aria-hidden="true">
        {data.peaks.map((peak, index) => (
          <span key={`${title}-${index}`} className="waveform-bar" style={{ height: `${Math.max(16, peak * 100)}%` }} />
        ))}
      </div>
    </section>
  );
}

export function SelectedFileWaveformPreview({
  file,
  copy,
}: {
  file: File | null;
  copy: AudioPreviewCopy;
}) {
  const [state, setState] = useState<InputPreviewState>({ status: "idle" });

  useEffect(() => {
    let disposed = false;

    if (!file) {
      setState({ status: "idle" });
      return () => {
        disposed = true;
      };
    }

    setState({ status: "loading" });

    void file
      .arrayBuffer()
      .then((arrayBuffer) => buildWaveformFromArrayBuffer(arrayBuffer))
      .then((data) => {
        if (!disposed) {
          setState({ status: "ready", data });
        }
      })
      .catch(() => {
        if (!disposed) {
          setState({ status: "error" });
        }
      });

    return () => {
      disposed = true;
    };
  }, [file]);

  if (!file) {
    return null;
  }

  if (state.status === "loading") {
    return <div className="preview-placeholder">{copy.previewLoading}</div>;
  }

  if (state.status === "error") {
    return <div className="preview-note">{copy.previewUnavailable}</div>;
  }

  if (state.status !== "ready") {
    return null;
  }

  return <WaveformBlock title={copy.inputWaveformTitle} durationLabel={copy.durationLabel} data={state.data} />;
}

export function OutputAudioPreview({
  downloadUrl,
  copy,
}: {
  downloadUrl: string;
  copy: AudioPreviewCopy;
}) {
  const [state, setState] = useState<OutputPreviewState>({ status: "loading" });

  useEffect(() => {
    let disposed = false;
    let audioUrl: string | null = null;

    setState({ status: "loading" });

    void downloadJobResult(downloadUrl)
      .then(async ({ blob }) => {
        const data = await buildWaveformFromArrayBuffer(await blob.arrayBuffer());
        audioUrl = URL.createObjectURL(blob);

        if (!disposed) {
          setState({
            status: "ready",
            data: {
              ...data,
              audioUrl,
            },
          });
          return;
        }

        URL.revokeObjectURL(audioUrl);
        audioUrl = null;
      })
      .catch(() => {
        if (!disposed) {
          setState({ status: "error" });
        }
      });

    return () => {
      disposed = true;

      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
    };
  }, [downloadUrl]);

  if (state.status === "loading") {
    return <div className="preview-placeholder">{copy.previewLoading}</div>;
  }

  if (state.status === "error") {
    return <div className="preview-note">{copy.previewFailed}</div>;
  }

  return (
    <div className="output-preview-stack">
      <WaveformBlock title={copy.outputWaveformTitle} durationLabel={copy.durationLabel} data={state.data} />

      <section className="preview-card">
        <div className="preview-header">
          <strong>{copy.outputAudioTitle}</strong>
        </div>
        <audio className="preview-audio" controls preload="metadata" src={state.data.audioUrl} />
      </section>
    </div>
  );
}
