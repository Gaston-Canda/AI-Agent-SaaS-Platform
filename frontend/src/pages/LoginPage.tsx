import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export function LoginPage(): JSX.Element {
  const navigate = useNavigate();
  const { isAuthenticated, login } = useAuth();
  const [tenantSlug, setTenantSlug] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  const submit = async (): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      await login({ tenantSlug, email, password });
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-4">
      <section className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900/80 p-6">
        <h1 className="text-lg font-semibold text-slate-100">Sign in</h1>
        <p className="mb-4 mt-1 text-sm text-slate-400">Access your tenant workspace.</p>
        <div className="space-y-3">
          <input
            value={tenantSlug}
            onChange={(event) => setTenantSlug(event.target.value)}
            placeholder="Tenant slug"
            className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
          />
          <input
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="Email"
            className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
          />
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Password"
            className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
          />
          <button
            type="button"
            onClick={() => void submit()}
            disabled={loading}
            className="w-full rounded-md bg-sky-600 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:bg-slate-700"
          >
            {loading ? "Signing in..." : "Login"}
          </button>
          {error ? <p className="text-xs text-rose-400">{error}</p> : null}
          <p className="text-xs text-slate-400">
            Need an account?{" "}
            <Link to="/register" className="text-sky-400 hover:text-sky-300">
              Register
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
