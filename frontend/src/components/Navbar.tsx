import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export function Navbar(): JSX.Element {
  const { user, logout } = useAuth();

  return (
    <header className="border-b border-slate-800 bg-slate-950/70 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link to="/dashboard" className="text-sm font-semibold tracking-wide text-slate-100">
          Agent Platform
        </Link>
        <div className="flex items-center gap-4">
          <Link to="/billing" className="text-xs text-slate-300 hover:text-white">
            Billing
          </Link>
          <span className="hidden text-xs text-slate-400 sm:inline">{user?.email}</span>
          <button
            type="button"
            onClick={logout}
            className="rounded-md border border-slate-700 px-3 py-1.5 text-xs text-slate-200 transition hover:border-slate-500"
          >
            Logout
          </button>
        </div>
      </div>
    </header>
  );
}
