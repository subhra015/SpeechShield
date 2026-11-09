// frontend/src/pages/Login.tsx
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(username, password);
      navigate("/dashboard");
    } catch {
      setError("Invalid credentials. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex bg-[var(--bg)]">
      <div className="hidden lg:flex flex-1 items-center justify-center p-12">
        <div className="max-w-md">
          <div className="text-sm uppercase tracking-widest text-[var(--text-muted)] mb-4">SpeechShield</div>
          <h1 className="text-4xl font-semibold leading-tight">Understand what's behind the voice.</h1>
          <p className="text-[var(--text-muted)] mt-4">Examine audio recordings for signs of synthetic speech with the V4 detection engine.</p>
        </div>
      </div>
      <div className="flex-1 flex items-center justify-center p-8">
        <form onSubmit={onSubmit} className="w-full max-w-sm space-y-5">
          <div>
            <h2 className="text-2xl font-semibold">Sign in</h2>
            <p className="text-sm text-[var(--text-muted)] mt-1">Access your audio analysis workspace.</p>
          </div>
          {error && <div className="text-sm text-[var(--danger)] bg-red-50 border border-red-200 rounded-lg p-3">{error}</div>}
          <div className="space-y-3">
            <input className="input" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
            <input className="input" type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </div>
          <button disabled={submitting} className="btn btn-primary w-full">
            {submitting ? "Signing in..." : "Sign in"}
          </button>
          <p className="text-sm text-[var(--text-muted)] text-center">
            No account? <Link to="/register" className="text-[var(--accent)] hover:underline">Create one</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
