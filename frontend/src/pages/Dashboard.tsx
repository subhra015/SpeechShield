// frontend/src/pages/Dashboard.tsx
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api } from "../api";

type Asset = {
  id: number;
  detected_format: string;
  file_size_bytes: number;
  duration_seconds: number;
  sample_rate: number;
  channels: number;
  original_filename: string | null;
  created_at: string;
};

export default function Dashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);

  async function loadAssets() {
    setLoading(true);
    setError("");
    try {
      const res = await api("/api/audio?limit=50&offset=0");
      if (!res.ok) throw new Error("Failed to load assets");
      const data = await res.json();
      setAssets(data.items || []);
    } catch {
      setError("Failed to load assets");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAssets();
  }, []);

  async function onUpload(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
      setError("File too large (max 10 MB)");
      return;
    }
    setUploading(true);
    setProgress(0);
    setError("");
    const form = new FormData();
    form.append("file", file);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", (import.meta.env.VITE_API_BASE_URL || "") + "/api/audio");
    xhr.withCredentials = true;
    // csrf
    const csrf = document.cookie.match(/speechshield_csrf=([^;]+)/)?.[1];
    if (csrf) xhr.setRequestHeader("X-CSRF-Token", decodeURIComponent(csrf));
    xhr.upload.onprogress = (ev) => {
      if (ev.lengthComputable) setProgress(Math.round((ev.loaded / ev.total) * 100));
    };
    xhr.onload = () => {
      setUploading(false);
      if (xhr.status >= 200 && xhr.status < 300) {
        loadAssets();
      } else {
        try {
          const j = JSON.parse(xhr.responseText);
          setError(j.detail || "Upload failed");
        } catch {
          setError("Upload failed");
        }
      }
    };
    xhr.onerror = () => {
      setUploading(false);
      setError("Network error");
    };
    xhr.send(form);
  }

  async function onDelete(id: number) {
    if (!confirm("Delete this asset?")) return;
    const res = await api(`/api/audio/${id}`, { method: "DELETE" });
    if (res.ok || res.status === 204) {
      loadAssets();
    } else {
      setError("Delete failed");
    }
  }

  async function onLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <div className="text-slate-100 space-y-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <div className="flex items-center gap-4">
          <span className="text-slate-400">{user?.username}</span>
          <button onClick={onLogout} className="bg-slate-700 px-3 py-1 rounded">Logout</button>
        </div>
      </div>

      <section className="mb-8 bg-slate-900 p-6 rounded">
        <h2 className="text-lg font-semibold mb-3">Upload audio (WAV/FLAC, max 10 MB)</h2>
        <form onSubmit={onUpload} className="space-y-3">
          <input ref={fileRef} type="file" accept=".wav,.flac,audio/wav,audio/flac" className="block" />
          {uploading && (
            <div className="w-full bg-slate-800 rounded h-2">
              <div className="bg-blue-600 h-2 rounded" style={{ width: `${progress}%` }} />
            </div>
          )}
          <button disabled={uploading} className="bg-blue-600 px-4 py-2 rounded disabled:opacity-50">
            {uploading ? `Uploading ${progress}%` : "Upload"}
          </button>
        </form>
        {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
      </section>

      <section>
        <h2 className="text-lg font-semibold mb-3">Your uploads</h2>
        {loading ? (
          <p className="text-slate-400">Loading...</p>
        ) : assets.length === 0 ? (
          <p className="text-slate-400">No uploads yet.</p>
        ) : (
          <ul className="space-y-2">
            {assets.map((a) => (
              <li key={a.id} className="bg-slate-900 p-4 rounded flex justify-between items-center">
                <div>
                  <div className="font-medium">{a.original_filename || `asset ${a.id}`}</div>
                  <div className="text-sm text-slate-400">
                    {a.detected_format} · {a.file_size_bytes} bytes · {a.duration_seconds.toFixed(2)}s · {a.sample_rate} Hz · {a.channels} ch
                  </div>
                </div>
                <button onClick={() => onDelete(a.id)} className="text-red-400 text-sm">Delete</button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
