import { Link, Outlet, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { useMe } from "../lib/auth";

interface PublicProvider {
  slug: string;
}

export default function AppShell() {
  const { me, signOut } = useMe();
  const navigate = useNavigate();
  const [hasProviders, setHasProviders] = useState(false);

  useEffect(() => {
    if (!me?.authenticated) {
      fetch("/api/auth/providers").then((r) => r.json()).then((rows: PublicProvider[]) => setHasProviders(rows.length > 0)).catch(() => setHasProviders(false));
    }
  }, [me?.authenticated]);

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <nav className="flex items-center gap-5">
            <Link to="/" className="font-semibold text-slate-950">SkillShelf</Link>
            {me?.authenticated && <Link to="/manage" className="text-sm text-slate-600 hover:text-slate-950">Manage</Link>}
            {me?.organizationAdmin && <Link to="/organization" className="text-sm text-slate-600 hover:text-slate-950">Organization</Link>}
          </nav>
          {me?.authenticated ? (
            <div className="flex items-center gap-3 text-sm">
              <div className="text-right">
                <p className="font-medium text-slate-900">{me.displayName}</p>
                <p className="text-xs text-slate-500">{me.email}</p>
              </div>
              <button onClick={() => signOut().then(() => navigate("/"))} className="rounded-md border border-slate-300 px-3 py-1.5 text-slate-700 hover:bg-slate-100">Sign out</button>
            </div>
          ) : hasProviders ? (
            <Link to="/login" className="rounded-md bg-slate-950 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800">Sign in</Link>
          ) : null}
        </div>
      </header>
      <Outlet />
    </div>
  );
}
