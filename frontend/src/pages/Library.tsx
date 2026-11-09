// frontend/src/pages/Library.tsx
import { useEffect, useState } from "react";
import { api } from "../api";

type Asset = { id: number; detected_format: string; file_size_bytes: number; duration_seconds: number; sample_rate: number; channels: number; original_filename: string | null; created_at: string };

export default function Library() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await api("/api/audio?limit=50&offset=0");
      if (!res.ok) throw new Error("fail");
      setAssets((await res.json()).items || []);
    } catch {
      setError("Failed to load assets");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function onDelete(id: number) {
    if (!confirm("Delete this asset?")) return;
    const res = await api(`/api/audio/${id}`, { method: "DELETE" });
    if (res.ok || res.status === 204) load();
    else setError("Delete failed");
  }

  const filtered = assets.filter((a) => {
    if (filter !== "all" && a.detected_format !== filter) return false;
    if (search && !(a.original_filename || "").toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Audio Library</h1>
      <div className="flex gap-3 flex-wrap">
        <input className="input max-w-xs" placeholder="Search..." value={search} onChange={(e) => setSearch(e.target.value)} />
        <select className="input max-w-xs" value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="all">All formats</option>
          <option value="WAV">WAV</option>
          <option value="FLAC">FLAC</option>
        </select>
      </div>
      {error && <p className="text-red-400 text-sm">{error}</p>}
      {loading ? (
        <div className="space-y-2"><div className="skeleton h-12" /><div className="skeleton h-12" /></div>
      ) : filtered.length === 0 ? (
        <div className="card text-center text-[var(--text-muted)]">No assets found.</div>
      ) : (
        <div className="space-y-2">
          {filtered.map((a) => (
            <div key={a.id} className="card flex justify-between items-center">
              <div>
                <div className="font-medium">{a.original_filename || `asset ${a.id}`}</div>
                <div className="text-xs text-[var(--text-muted)] font-mono">
                  {a.detected_format} · {a.file_size_bytes} B · {a.duration_seconds.toFixed(2)}s · {a.sample_rate} Hz · {a.channels} ch · {new Date(a.created_at).toLocaleString()}
                </div>
              </div>
              <button onClick={() => onDelete(a.id)} className="text-red-400 text-sm">Delete</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
