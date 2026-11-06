import { useEffect, useState } from "react";
import { API_BASE_URL } from "./config";

type Health = { application: string; model_ready: boolean; model_error: string | null; status: string };
type ModelInfo = {
  model_version: string;
  architecture: string;
  checkpoint_sha256: string | null;
  sha256_verified: boolean;
  inference_status: string;
  inference_production_ready: boolean;
};

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [info, setInfo] = useState<ModelInfo | null>(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/health`).then((r) => r.json()).then(setHealth).catch(() => setHealth(null));
    fetch(`${API_BASE_URL}/api/model/info`).then((r) => r.json()).then(setInfo).catch(() => setInfo(null));
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-8">
      <h1 className="text-2xl font-bold mb-4">SpeechShield (Layer 0)</h1>
      <p className="text-slate-400 mb-6">
        Foundation only. No inference endpoint is exposed (preprocessing parity unverified).
      </p>

      <section className="mb-6">
        <h2 className="text-lg font-semibold mb-2">Health</h2>
        <pre className="bg-slate-900 p-4 rounded text-sm">{JSON.stringify(health, null, 2)}</pre>
      </section>

      <section>
        <h2 className="text-lg font-semibold mb-2">Model Info (safe metadata)</h2>
        <pre className="bg-slate-900 p-4 rounded text-sm">{JSON.stringify(info, null, 2)}</pre>
      </section>
    </div>
  );
}
