// frontend/src/pages/Dashboard.tsx (Overview)
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api } from "../api";

type Asset = { id: number; detected_format: string; file_size_bytes: number; duration_seconds: number; created_at: string; original_filename: string | null };

export default function Dashboard() {
  const { user } = useAuth();
  const [assets, setAssets] = useState<Asset[]>([]);
  const [jobs, setJobs] = useState<Array<{ status?: string }>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const r = await api("/api/audio?limit=5&offset=0");
        if (r.ok) setAssets((await r.json()).items || []);
        const j = await api("/api/jobs?limit=5&offset=0");
        if (j.ok) setJobs((await j.json()).items || []);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Understand what's behind the voice.</h1>
        <p className="text-[var(--text-muted)] mt-2 max-w-2xl">
          Examine audio recordings for signs of synthetic speech with SpeechShield's V4 detection engine.
        </p>
        <Link to="/dashboard/analyze" className="btn btn-primary mt-4 inline-flex">Analyze a recording</Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card">
          <div className="text-xs text-[var(--text-muted)] uppercase tracking-wider">Recordings</div>
          <div className="text-3xl font-bold mt-2">{loading ? "…" : assets.length}</div>
        </div>
        <div className="card">
          <div className="text-xs text-[var(--text-muted)] uppercase tracking-wider">Recent jobs</div>
          <div className="text-3xl font-bold mt-2">{loading ? "…" : jobs.length}</div>
        </div>
        <div className="card">
          <div className="text-xs text-[var(--text-muted)] uppercase tracking-wider">Blocked</div>
          <div className="text-3xl font-bold mt-2">{loading ? "…" : jobs.filter((j) => j.status?.includes("BLOCKED")).length}</div>
        </div>
        <div className="card">
          <div className="text-xs text-[var(--text-muted)] uppercase tracking-wider">Failed</div>
          <div className="text-3xl font-bold mt-2">{loading ? "…" : jobs.filter((j) => j.status === "FAILED").length}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="font-semibold mb-3">Recent recordings</h2>
          {loading ? (
            <div className="space-y-2"><div className="skeleton h-10" /><div className="skeleton h-10" /></div>
          ) : assets.length === 0 ? (
            <p className="text-[var(--text-muted)] text-sm">No recordings yet. Upload one to get started.</p>
          ) : (
            <ul className="space-y-2">
              {assets.map((a) => (
                <li key={a.id} className="flex justify-between text-sm">
                  <span>{a.original_filename || `asset ${a.id}`}</span>
                  <span className="text-[var(--text-muted)]">{a.detected_format} · {a.duration_seconds.toFixed(1)}s</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="card">
          <h2 className="font-semibold mb-3">System status</h2>
          <ul className="space-y-2 text-sm">
            <li className="flex justify-between"><span>Backend</span><span className="badge badge-success">Connected</span></li>
            <li className="flex justify-between"><span>Session</span><span className="badge badge-success">Authenticated</span></li>
            <li className="flex justify-between"><span>Upload</span><span className="badge badge-success">Available</span></li>
            <li className="flex justify-between"><span>Inference</span><span className="badge badge-warn">Blocked (authorization pending)</span></li>
          </ul>
          <p className="text-xs text-[var(--text-muted)] mt-3">Signed in as {user?.username}</p>
        </div>
      </div>
    </div>
  );
}
