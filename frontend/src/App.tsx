// frontend/src/App.tsx
import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import { ProtectedRoute } from "./components/ProtectedRoute";

function Shell() {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen flex">
      <aside className="w-60 bg-[var(--bg-1)] border-r border-[var(--border)] p-4 flex flex-col gap-2">
        <div className="flex items-center gap-2 mb-6">
          <div className="w-8 h-8 rounded-lg bg-[var(--accent)] flex items-center justify-center text-[#0a0e1a] font-bold">S</div>
          <span className="font-semibold tracking-tight">SpeechShield</span>
        </div>
        <nav className="flex flex-col gap-1">
          <a href="/dashboard" className="px-3 py-2 rounded hover:bg-[var(--surface-2)]">Dashboard</a>
        </nav>
        <div className="mt-auto">
          <div className="text-sm text-[var(--text-muted)] mb-2">{user?.username}</div>
          <button onClick={logout} className="btn btn-ghost w-full">Logout</button>
        </div>
      </aside>
      <main className="flex-1 p-8 overflow-auto">
        <Outlet />
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
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
