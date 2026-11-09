// frontend/src/pages/History.tsx
import { useEffect, useState } from "react";
import { api } from "../api";

type Run = { id: number; status: string; audio_asset_id: number; model_id: string; spoof_probability: number | null; threshold: number | null; predicted_class: number | null; created_at: string; completed_at: string | null; error_message: string | null };

export default function History() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const r = await api("/api/inference?limit=50&offset=0");
        if (!r.ok) throw new Error("fail");
        setRuns((await r.json()).items || []);
      } catch {
        setError("Failed to load history");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Analysis History</h1>
      {error && <p className="text-red-400 text-sm">{error}</p>}
      {loading ? (
        <div className="space-y-2"><div className="skeleton h-12" /><div className="skeleton h-12" /></div>
      ) : runs.length === 0 ? (
        <div className="card text-center text-[var(--text-muted)]">No analysis runs yet.</div>
      ) : (
        <div className="space-y-2">
          {runs.map((r) => (
            <div key={r.id} className="card flex justify-between items-center">
              <div>
                <div className="font-medium">Run #{r.id} · asset {r.audio_asset_id}</div>
                <div className="text-xs text-[var(--text-muted)]">
                  {r.status} · {new Date(r.created_at).toLocaleString()}
                  {r.spoof_probability !== null && ` · probability ${r.spoof_probability}`}
                </div>
                {r.error_message && <div className="text-xs text-red-400 mt-1">{r.error_message}</div>}
              </div>
              <span className="badge">{r.status}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
