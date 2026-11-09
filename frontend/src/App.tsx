// frontend/src/App.tsx
import { BrowserRouter, Routes, Route, Navigate, Outlet, NavLink, useNavigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Analyze from "./pages/Analyze";
import Library from "./pages/Library";
import History from "./pages/History";
import { ProtectedRoute } from "./components/ProtectedRoute";

function Shell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  return (
    <div className="min-h-screen flex bg-[var(--bg)]">
      <aside className="w-60 shrink-0 border-r border-[var(--border)] bg-[var(--surface)] flex flex-col">
        <div className="p-5 flex items-center gap-3 border-b border-[var(--border)]">
          <div className="w-9 h-9 rounded-lg bg-[var(--text)] text-white flex items-center justify-center font-bold text-sm">S</div>
          <div>
            <div className="font-semibold tracking-tight">SpeechShield</div>
            <div className="text-xs text-[var(--text-muted)]">Audio forensics</div>
          </div>
        </div>
        <nav className="p-3 flex flex-col gap-1">
          {[
            { to: "/dashboard", label: "Overview" },
            { to: "/dashboard/analyze", label: "Analyze" },
            { to: "/dashboard/library", label: "Library" },
            { to: "/dashboard/history", label: "History" },
          ].map((n) => (
            <NavLink key={n.to} to={n.to} className={({ isActive }) =>
              `px-3 py-2 rounded-lg text-sm transition ${isActive ? "bg-[var(--surface-2)] text-[var(--text)] font-medium" : "text-[var(--text-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]"}`
            }>{n.label}</NavLink>
          ))}
        </nav>
        <div className="mt-auto p-4 border-t border-[var(--border)]">
          <div className="text-xs text-[var(--text-muted)] mb-2">{user?.username} · local</div>
          <button onClick={async () => { await logout(); navigate("/login"); }} className="btn btn-ghost w-full text-sm">Sign out</button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <div className="max-w-6xl mx-auto p-8"><Outlet /></div>
      </main>
    </div>
  );
}

function Home() {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-8">Loading...</div>;
  return user ? <Navigate to="/dashboard" replace /> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/dashboard" element={<ProtectedRoute><Shell /></ProtectedRoute>}>
            <Route index element={<Dashboard />} />
            <Route path="analyze" element={<Analyze />} />
            <Route path="library" element={<Library />} />
            <Route path="history" element={<History />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
