import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useMe } from "../lib/auth";

export default function ManageGate({ children }: { children: ReactNode }) {
  const { me, loading } = useMe();
  const location = useLocation();
  if (loading || !me) return <div className="p-8 text-sm text-slate-500">Loading...</div>;
  if (!me.authenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (!me.organizationAdmin && !me.canCreateMarketplace && me.marketplaceAdminSlugs.length === 0 && me.marketplaceMaintainerSlugs.length === 0 && me.marketplaceContributorSlugs.length === 0) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}
