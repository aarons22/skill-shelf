import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export interface Me {
  authenticated: boolean;
  id?: number | null;
  email?: string | null;
  displayName?: string | null;
  user?: { id: number; email: string; displayName: string; provider?: string | null } | null;
  organizationAdmin: boolean;
  workspaceAdmin?: boolean;
  marketplaceAdminSlugs: string[];
  loginConfigured: boolean;
  bootstrapRequired: boolean;
  bootstrapCompleted: boolean;
  mustChangePassword: boolean;
  accessMode: "public" | "authenticated" | "restricted";
  marketplaceCreation: "authenticated" | "organization_admin";
}

interface AuthContextValue {
  me: Me | null;
  loading: boolean;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    const res = await fetch("/api/me");
    setMe(await res.json());
  };

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, []);

  const signOut = async () => {
    await fetch("/auth/logout", { method: "POST", redirect: "manual" });
    await refresh();
  };

  const value = useMemo(() => ({ me, loading, refresh, signOut }), [me, loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useMe() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useMe must be used inside AuthProvider");
  return value;
}
