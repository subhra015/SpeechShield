// frontend/src/pages/Analyze.tsx
import { useEffect, useRef, useState } from "react";
import { api } from "../api";

type Asset = { id: number; detected_format: string; file_size_bytes: number; duration_seconds: number; sample_rate: number; channels: number; original_filename: string | null };

export default function Analyze() {
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [asset, setAsset] = useState<Asset | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [inferenceStatus, setInferenceStatus] = useState<string | null>(null);
  type Result = {
    spoof_probability: number;
    threshold: number;
    predicted_class: number;
    model_id: string;
    checkpoint_sha256: string;
    waveform_preview: string;
    feature_map_preview: string;
    evaluated_segment_start: number;
    evaluated_segment_end: number;
    model_input_shape: string;
    preprocessing_device: string;
    inference_device: string;
  };
  const [result, setResult] = useState<Result | null>(null);
  const [blockedMsg, setBlockedMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // nothing
  }, []);

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    setError("");
    setAsset(null);
    setJobStatus(null);
    setInferenceStatus(null);
    setResult(null);
    setBlockedMsg("");
    const f = e.target.files?.[0];
    if (!f) return;
    const ext = f.name.toLowerCase().split(".").pop();
    if (ext !== "wav" && ext !== "flac") {
      setError("Only WAV and FLAC files are supported.");
      return;
    }
    if (f.size > 10 * 1024 * 1024) {
      setError("File exceeds 10 MB limit.");
      return;
    }
    setFile(f);
  }

  async function onUpload() {
    if (!file) return;
    setUploading(true);
    setProgress(0);
    setError("");
    const form = new FormData();
    form.append("file", file);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", (import.meta.env.VITE_API_BASE_URL || "") + "/api/audio");
    xhr.withCredentials = true;
    const csrf = document.cookie.match(/speechshield_csrf=([^;]+)/)?.[1];
    if (csrf) xhr.setRequestHeader("X-CSRF-Token", decodeURIComponent(csrf));
    xhr.upload.onprogress = (ev) => {
      if (ev.lengthComputable) setProgress(Math.round((ev.loaded / ev.total) * 100));
    };
    xhr.onload = () => {
      setUploading(false);
      if (xhr.status >= 200 && xhr.status < 300) {
        setAsset(JSON.parse(xhr.responseText));
      } else {
        try {
          setError(JSON.parse(xhr.responseText).detail || "Upload failed");
        } catch {
          setError("Upload failed");
        }
      }
    };
    xhr.onerror = () => { setUploading(false); setError("Network error"); };
    xhr.send(form);
  }

  async function onAnalyze() {
    if (!asset) return;
    setError("");
    setJobStatus("QUEUED");
    setInferenceStatus(null);
    setResult(null);
    setBlockedMsg("");
    // create job
    const jr = await api(`/api/audio/${asset.id}/jobs`, { method: "POST" });
    if (!jr.ok) { setError("Failed to create job"); setJobStatus("FAILED"); return; }
    const job = await jr.json();
    setJobStatus(job.status);
    // request inference
    const ir = await api(`/api/jobs/${job.id}/inference`, { method: "POST" });
    if (ir.status === 423) {
      const b = await ir.json().catch(() => ({}));
      setInferenceStatus("BLOCKED_PENDING_AUTHORIZATION");
      setBlockedMsg(b.detail || "Analysis is currently unavailable. The recording has been uploaded and validated. The V4 inference authorization is currently disabled.");
      // refresh job
      const gr = await api(`/api/jobs/${job.id}`);
      if (gr.ok) setJobStatus((await gr.json()).status);
      return;
    }
    if (!ir.ok) {
      setError("Inference request failed");
      setInferenceStatus("FAILED");
      return;
    }
    const run = await ir.json();
    setInferenceStatus(run.status);
    if (run.status === "COMPLETED") {
      setResult(run);
    }
    const gr = await api(`/api/jobs/${job.id}`);
    if (gr.ok) setJobStatus((await gr.json()).status);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Analyze Audio</h1>

      <div className="card">
        <h2 className="font-semibold mb-3">1. Select recording</h2>
        <div
          className="border-2 border-dashed border-[var(--border)] rounded-lg p-8 text-center cursor-pointer hover:border-[var(--accent)] transition"
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const f = e.dataTransfer.files?.[0];
            if (f) {
              const input = fileRef.current;
              if (input) {
                const dt = new DataTransfer();
                dt.items.add(f);
                input.files = dt.files;
                input.dispatchEvent(new Event("change", { bubbles: true }));
              }
            }
          }}
        >
          <input ref={fileRef} type="file" accept=".wav,.flac,audio/wav,audio/flac" className="hidden" onChange={onFileChange} />
          <p className="text-[var(--text-muted)]">Drag and drop a WAV or FLAC file here, or click to browse</p>
          <p className="text-xs text-[var(--text-muted)] mt-1">Max 10 MB</p>
        </div>
        {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
        {file && (
          <div className="mt-3 text-sm text-[var(--text-muted)]">
            Selected: {file.name} ({(file.size / 1024).toFixed(1)} KB)
          </div>
        )}
        {file && !asset && (
          <button onClick={onUpload} disabled={uploading} className="btn btn-primary mt-3">
            {uploading ? `Uploading ${progress}%` : "Upload"}
          </button>
        )}
        {uploading && (
          <div className="w-full bg-[var(--bg-1)] rounded h-2 mt-2">
            <div className="bg-[var(--accent)] h-2 rounded" style={{ width: `${progress}%` }} />
          </div>
        )}
      </div>

      {asset && (
        <div className="card">
          <h2 className="font-semibold mb-3">2. Selected recording</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <div><div className="text-[var(--text-muted)] text-xs">Format</div><div>{asset.detected_format}</div></div>
            <div><div className="text-[var(--text-muted)] text-xs">Size</div><div>{asset.file_size_bytes} B</div></div>
            <div><div className="text-[var(--text-muted)] text-xs">Duration</div><div>{asset.duration_seconds.toFixed(2)}s</div></div>
            <div><div className="text-[var(--text-muted)] text-xs">Sample rate</div><div>{asset.sample_rate} Hz</div></div>
            <div><div className="text-[var(--text-muted)] text-xs">Channels</div><div>{asset.channels}</div></div>
            <div><div className="text-[var(--text-muted)] text-xs">Filename</div><div className="truncate">{asset.original_filename}</div></div>
          </div>
          <button onClick={onAnalyze} className="btn btn-primary mt-4">Analyze audio</button>
        </div>
      )}

      {(jobStatus || inferenceStatus) && (
        <div className="card">
          <h2 className="font-semibold mb-3">3. Analysis status</h2>
          <div className="space-y-2 text-sm">
            {jobStatus && <div>Job status: <span className="badge">{jobStatus}</span></div>}
            {inferenceStatus && <div>Inference status: <span className="badge">{inferenceStatus}</span></div>}
          </div>
          {blockedMsg && (
            <div className="mt-3 p-3 rounded bg-[var(--surface-2)] border border-[var(--border)]">
              <div className="font-semibold text-[var(--warn)]">Analysis is currently unavailable.</div>
              <div className="text-sm text-[var(--text-muted)] mt-1">{blockedMsg}</div>
            </div>
          )}
          {result && (
            <div className="mt-3 space-y-4">
              <div className="p-4 rounded bg-[var(--surface-2)] border border-[var(--border)]">
                <div className="text-2xl font-bold">
                  {result.predicted_class === 0 ? "LIKELY GENUINE" : "LIKELY SYNTHETIC"}
                </div>
                <div className="text-sm text-[var(--text-muted)] mt-1">
                  Spoof probability: {(result.spoof_probability * 100).toFixed(6)}% · Threshold: {(result.threshold * 100).toFixed(1)}%
                </div>
                <div className="text-sm text-[var(--text-muted)]">
                  Model: {result.model_id} · Checkpoint: {result.checkpoint_sha256?.slice(0, 12)}…
                </div>
                <p className="text-xs text-[var(--text-muted)] mt-2">
                  SpeechShield's prediction is a model assessment, not proof of authenticity.
                </p>
              </div>

              {/* Score gauge */}
              <div className="card">
                <div className="text-sm font-semibold mb-2">Spoof score vs threshold</div>
                <div className="relative h-6 bg-[var(--bg-1)] rounded">
                  <div
                    className="absolute top-0 h-6 bg-[var(--accent)] rounded-l"
                    style={{ width: `${Math.min(100, result.spoof_probability * 100)}%` }}
                  />
                  <div
                    className="absolute top-0 h-6 w-0.5 bg-[var(--warn)]"
                    style={{ left: `${result.threshold * 100}%` }}
                    title={`Threshold ${(result.threshold * 100).toFixed(1)}%`}
                  />
                </div>
                <div className="flex justify-between text-xs text-[var(--text-muted)] mt-1">
                  <span>0% genuine</span>
                  <span className="text-[var(--warn)]">threshold {(result.threshold * 100).toFixed(1)}%</span>
                  <span>100% synthetic</span>
                </div>
                <p className="text-xs text-[var(--text-muted)] mt-2">
                  Scores below the threshold are classified as genuine. Scores at or above the threshold are classified as synthetic.
                </p>
              </div>

              {/* Waveform */}
              {result.waveform_preview && (
                <div className="card">
                  <div className="text-sm font-semibold mb-2">Evaluated V4 audio segment — 4 seconds</div>
                  <svg viewBox="0 0 512 120" className="w-full" preserveAspectRatio="none">
                    {JSON.parse(result.waveform_preview).map((v: number, i: number, arr: number[]) => {
                      const x = (i / (arr.length - 1)) * 512;
                      const y = 60 - v * 40;
                      return <line key={i} x1={x} y1={60} x2={x} y2={y} stroke="var(--accent)" strokeWidth="1" />;
                    })}
                  </svg>
                  <div className="text-xs text-[var(--text-muted)] mt-1">Time (s): 0 → 4</div>
                </div>
              )}

              {/* Feature map */}
              {result.feature_map_preview && (
                <div className="card">
                  <div className="text-sm font-semibold mb-2">V4 Log-Mel Input Feature Map</div>
                  <canvas
                    ref={(el) => {
                      if (!el) return;
                      const ctx = el.getContext("2d");
                      if (!ctx) return;
                      const fm = JSON.parse(result.feature_map_preview) as number[][];
                      const rows = fm.length;
                      const cols = fm[0].length;
                      el.width = cols;
                      el.height = rows;
                      const img = ctx.createImageData(cols, rows);
                      for (let r = 0; r < rows; r++) {
                        for (let c = 0; c < cols; c++) {
                          const v = fm[r][c];
                          const t = Math.max(0, Math.min(1, (v + 3) / 6));
                          const idx = (r * cols + c) * 4;
                          img.data[idx] = Math.round(t * 200);
                          img.data[idx + 1] = Math.round(t * 230);
                          img.data[idx + 2] = Math.round(t * 180);
                          img.data[idx + 3] = 255;
                        }
                      }
                      ctx.putImageData(img, 0, 0);
                    }}
                    className="w-full h-32 rounded border border-[var(--border)]"
                    style={{ imageRendering: "pixelated" }}
                  />
                  <div className="text-xs text-[var(--text-muted)] mt-1">Frequency bins (64) × time (96 downsampled from 401). 4-second model window.</div>
                </div>
              )}

              {/* Diagnostics */}
              <div className="card">
                <div className="text-sm font-semibold mb-2">Technical diagnostics</div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="text-[var(--text-muted)]">Model input shape</div><div className="font-mono">{result.model_input_shape}</div>
                  <div className="text-[var(--text-muted)]">Evaluated segment</div><div>{result.evaluated_segment_start}s – {result.evaluated_segment_end}s</div>
                  <div className="text-[var(--text-muted)]">Preprocessing device</div><div>{result.preprocessing_device}</div>
                  <div className="text-[var(--text-muted)]">Inference device</div><div>{result.inference_device}</div>
                  <div className="text-[var(--text-muted)]">Model</div><div>{result.model_id}</div>
                  <div className="text-[var(--text-muted)]">Checkpoint</div><div className="font-mono truncate">{result.checkpoint_sha256}</div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
