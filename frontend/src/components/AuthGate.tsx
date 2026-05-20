import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useMe } from "../lib/auth";

export default function AuthGate({ children }: { children: ReactNode }) {
  const { me, loading } = useMe();
  const location = useLocation();
  if (loading || !me) return <div className="p-8 text-sm text-slate-500">Loading...</div>;
  if (me.bootstrapRequired && location.pathname !== "/setup") {
    return <Navigate to="/setup" replace />;
  }
  if (!me.bootstrapRequired && location.pathname === "/setup") {
    return <Navigate to="/login" replace />;
  }
  if (me.mustChangePassword && location.pathname !== "/change-password") {
    return <Navigate to="/change-password" replace />;
  }
  if (!me.authenticated && me.accessMode !== "public" && location.pathname !== "/login" && location.pathname !== "/setup") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}
