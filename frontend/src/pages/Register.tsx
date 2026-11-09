// frontend/src/pages/Register.tsx
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
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
    <div className="min-h-screen flex bg-[var(--bg)]">
      <div className="flex-1 flex items-center justify-center p-8">
        <form onSubmit={onSubmit} className="w-full max-w-sm space-y-5">
          <div>
            <h2 className="text-2xl font-semibold">Create account</h2>
            <p className="text-sm text-[var(--text-muted)] mt-1">Start analyzing audio recordings.</p>
          </div>
          {error && <div className="text-sm text-[var(--danger)] bg-red-50 border border-red-200 rounded-lg p-3">{error}</div>}
          <div className="space-y-3">
            <input className="input" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
            <input className="input" type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            <input className="input" type="password" placeholder="Password (min 8)" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
          </div>
          <button disabled={submitting} className="btn btn-primary w-full">
            {submitting ? "Creating..." : "Create account"}
          </button>
          <p className="text-sm text-[var(--text-muted)] text-center">
            Have an account? <Link to="/login" className="text-[var(--accent)] hover:underline">Sign in</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
