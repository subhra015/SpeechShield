// frontend/src/pages/Register.tsx
import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await register(username, email, password);
      navigate("/dashboard");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Registration failed";
      setError(msg || "Registration failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center text-slate-100" style={{ background: "var(--bg-0)" }}>
      <form onSubmit={onSubmit} className="card w-96 space-y-4">
        <h1 className="text-xl font-bold">Register</h1>
        {error && <p className="text-red-400 text-sm">{error}</p>}
        <input className="w-full p-2 rounded bg-slate-800" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
        <input className="w-full p-2 rounded bg-slate-800" type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input className="w-full p-2 rounded bg-slate-800" type="password" placeholder="Password (min 8)" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button disabled={submitting} className="w-full bg-blue-600 p-2 rounded disabled:opacity-50">
          {submitting ? "Creating..." : "Create account"}
        </button>
        <p className="text-sm text-slate-400">Have an account? <Link to="/login" className="text-blue-400">Sign in</Link></p>
      </form>
    </div>
  );
}
