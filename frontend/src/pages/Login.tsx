// frontend/src/pages/Login.tsx
import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
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
      setError("Invalid credentials");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center text-slate-100" style={{ background: "var(--bg-0)" }}>
      <form onSubmit={onSubmit} className="card w-96 space-y-4">
        <h1 className="text-xl font-bold">Login</h1>
        {error && <p className="text-red-400 text-sm">{error}</p>}
        <input className="w-full p-2 rounded bg-slate-800" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
        <input className="w-full p-2 rounded bg-slate-800" type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button disabled={submitting} className="w-full bg-blue-600 p-2 rounded disabled:opacity-50">
          {submitting ? "Signing in..." : "Sign in"}
        </button>
        <p className="text-sm text-slate-400">No account? <Link to="/register" className="text-blue-400">Register</Link></p>
      </form>
    </div>
  );
}
