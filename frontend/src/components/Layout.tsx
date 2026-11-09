// frontend/src/components/Layout.tsx
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const nav = [
  { to: "/dashboard", label: "Overview", icon: "◎" },
  { to: "/dashboard/analyze", label: "Analyze Audio", icon: "◆" },
  { to: "/dashboard/library", label: "Audio Library", icon: "  " },
  { to: "/dashboard/history", label: "Analysis History", icon: "  " },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  return (
    <div className="min-h-screen flex bg-[var(--bg-0)] text-[var(--text)]">
      <aside className="w-60 shrink-0 border-r border-[var(--border)] bg-[var(--bg-1)] flex flex-col">
        <div className="p-5 flex items-center gap-3 border-b border-[var(--border)]">
          <div className="w-9 h-9 rounded-lg bg-[var(--accent)] text-[#0a0e1a] flex items-center justify-center font-bold">S</div>
          <div>
            <div className="font-semibold tracking-tight">SpeechShield</div>
            <div className="text-xs text-[var(--text-muted)]">Audio forensics</div>
          </div>
        </div>
        <nav className="p-3 flex flex-col gap-1">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className={({ isActive }) =>
                `px-3 py-2 rounded-lg text-sm flex items-center gap-3 transition ${isActive ? "bg-[var(--surface-2)] text-[var(--text)]" : "text-[var(--text-muted)] hover:bg-[var(--surface)]"}`
              }
            >
              <span className="w-5 text-center">{n.icon}</span>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto p-4 border-t border-[var(--border)]">
          <div className="text-sm mb-2">{user?.username}</div>
          <button
            onClick={async () => { await logout(); navigate("/login"); }}
            className="btn btn-ghost w-full text-sm"
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <div className="max-w-6xl mx-auto p-8">{children}</div>
      </main>
    </div>
  );
}
