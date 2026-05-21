import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import CopyLine from "../components/CopyLine";

interface CurrentUser {
  authenticated: boolean;
  organizationAdmin: boolean;
  publicBaseUrl: string;
}

interface OrganizationSettings {
  accessMode: "public" | "authenticated" | "restricted";
}

interface AuthProvider {
  slug: string;
  displayName: string;
  providerType: "local" | "github" | "oidc" | "trusted_header" | "trusted_headers";
  enabled: boolean;
  clientId: string;
  secretConfigured: boolean;
  issuerUrl?: string | null;
  authorizationUrl?: string | null;
  tokenUrl?: string | null;
  userinfoUrl?: string | null;
  scopes: string;
  groupClaim?: string | null;
  allowedOrgs?: string | null;
  allowlist?: Record<string, unknown> | null;
  loginUrl: string;
  callbackUrl?: string | null;
}

interface OrgUser {
  id: number;
  email: string;
  displayName: string;
  provider: string;
  organizationRole: "organization_admin" | "marketplace_creator" | "viewer";
  disabledAt?: number | null;
  mustChangePassword: boolean;
}

interface AccessToken {
  id: number;
  name: string;
  scope: string;
  marketplaceSlug: string | null;
  createdAt: number;
  revokedAt: number | null;
}

type Tab = "access" | "auth" | "users" | "tokens";

function emptyProviderFor(type: "github" | "oidc" | "trusted_header") {
  if (type === "github") {
    return {
      slug: "github",
      displayName: "GitHub",
      providerType: "github" as const,
      enabled: true,
      clientId: "",
      clientSecret: "",
      issuerUrl: "",
      authorizationUrl: "",
      tokenUrl: "",
      userinfoUrl: "",
      scopes: "",
      groupClaim: "",
      allowedOrgs: "",
    };
  }
  if (type === "oidc") {
    return {
      slug: "oidc",
      displayName: "SSO",
      providerType: "oidc" as const,
      enabled: true,
      clientId: "",
      clientSecret: "",
      issuerUrl: "",
      authorizationUrl: "",
      tokenUrl: "",
      userinfoUrl: "",
      scopes: "openid email profile",
      groupClaim: "",
      allowedOrgs: "",
    };
  }
  return {
    slug: "trusted-header",
    displayName: "Trusted proxy",
    providerType: "trusted_header" as const,
    enabled: true,
    clientId: "",
    clientSecret: "",
    issuerUrl: "",
    authorizationUrl: "",
    tokenUrl: "",
    userinfoUrl: "",
    scopes: "",
    groupClaim: "",
    allowedOrgs: "",
  };
}

type ProviderFormState = ReturnType<typeof emptyProviderFor>;

export default function OrganizationAdmin() {
  const location = useLocation();
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [settings, setSettings] = useState<OrganizationSettings | null>(null);
  const [providers, setProviders] = useState<AuthProvider[]>([]);
  const [users, setUsers] = useState<OrgUser[]>([]);
  const [newUserEmail, setNewUserEmail] = useState("");
  const [newUserName, setNewUserName] = useState("");
  const [tempPassword, setTempPassword] = useState("");
  const [message, setMessage] = useState("");
  const [providerForm, setProviderForm] = useState<ProviderFormState | null>(null);
  const [loading, setLoading] = useState(true);
  const [tokens, setTokens] = useState<AccessToken[]>([]);
  const [newTokenName, setNewTokenName] = useState("CI read access");
  const [createdToken, setCreatedToken] = useState("");

  const tab: Tab = (() => {
    if (location.pathname.endsWith("/auth")) return "auth";
    if (location.pathname.endsWith("/users")) return "users";
    if (location.pathname.endsWith("/tokens")) return "tokens";
    return "access";
  })();

  const load = async () => {
    setLoading(true);
    const meRes = await fetch("/api/me");
    const meData = await meRes.json();
    setMe(meData);
    if (!meData.organizationAdmin) {
      setLoading(false);
      return;
    }
    const [settingsRes, providersRes, usersRes, tokensRes] = await Promise.all([
      fetch("/api/organization/settings"),
      fetch("/api/organization/auth-providers"),
      fetch("/api/organization/users"),
      fetch("/api/access-tokens"),
    ]);
    setSettings(await settingsRes.json());
    setProviders(providersRes.ok ? await providersRes.json() : []);
    setUsers(usersRes.ok ? await usersRes.json() : []);
    setTokens(tokensRes.ok ? await tokensRes.json() : []);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const saveSettings = async (updates: Partial<OrganizationSettings>) => {
    if (!settings) return;
    const next = { ...settings, ...updates };
    setSettings(next);
    setMessage("");
    const r = await fetch("/api/organization/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(next),
    });
    setMessage(r.ok ? "Saved." : "Save failed.");
    if (!r.ok) setSettings(settings);
  };

  const saveProvider = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!providerForm) return;
    setMessage("");
    const r = await fetch("/api/organization/auth-providers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(providerForm),
    });
    setMessage(r.ok ? "Provider saved." : "Could not save provider.");
    if (r.ok) {
      setProviderForm(null);
      load();
    }
  };

  const updateProvider = async (provider: AuthProvider, updates: Partial<AuthProvider>) => {
    const r = await fetch(`/api/organization/auth-providers/${provider.slug}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
    setMessage(r.ok ? "Provider updated." : "Could not update provider.");
    if (r.ok) load();
  };

  const deleteProvider = async (provider: AuthProvider) => {
    if (!confirm(`Delete login provider "${provider.displayName}"?`)) return;
    const r = await fetch(`/api/organization/auth-providers/${provider.slug}`, { method: "DELETE" });
    setMessage(r.ok ? "Provider deleted." : "Could not delete provider.");
    if (r.ok) load();
  };

  const updateUserRole = async (user: OrgUser, organizationRole: OrgUser["organizationRole"]) => {
    const r = await fetch(`/api/organization/users/${user.id}/role`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ organizationRole }),
    });
    setMessage(r.ok ? "User role updated." : "Could not update user role.");
    if (r.ok) load();
  };

  const createToken = async () => {
    setCreatedToken("");
    const r = await fetch("/api/access-tokens", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newTokenName }),
    });
    if (r.ok) {
      const data = await r.json();
      setCreatedToken(data.token);
      setNewTokenName("CI read access");
      load();
    }
  };

  const revokeToken = async (tokenId: number) => {
    if (!confirm("Revoke this token? Agents using it will lose access immediately.")) return;
    await fetch(`/api/access-tokens/${tokenId}`, { method: "DELETE" });
    load();
  };

  if (loading) return <div className="p-8 text-sm text-slate-500">Loading...</div>;
  if (!me?.organizationAdmin) {
    return (
      <div className="min-h-screen bg-slate-50">
        <main className="mx-auto max-w-2xl px-4 py-16">
          <h1 className="text-xl font-semibold text-slate-950">Organization settings</h1>
          <p className="mt-3 text-sm text-slate-600">You need organization admin access to view this area.</p>
          <Link to="/manage" className="mt-6 inline-block text-sm font-medium text-slate-950 hover:underline">Back to marketplaces</Link>
        </main>
      </div>
    );
  }

  const TABS: { id: Tab; label: string; path: string }[] = [
    { id: "access", label: "Access", path: "/organization" },
    { id: "auth", label: "Auth", path: "/organization/auth" },
    { id: "users", label: "Users", path: "/organization/users" },
    { id: "tokens", label: "Tokens", path: "/organization/tokens" },
  ];

  return (
    <div>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <h1 className="mb-1 text-lg font-semibold text-slate-950">Organization settings</h1>
        <p className="mb-6 text-xs text-slate-500">Access, login, and tenant-wide controls</p>
        <div className="mb-6 flex gap-6 border-b border-slate-200">
          {TABS.map(({ id, label, path }) => (
            <Link
              key={id}
              to={path}
              className={`pb-2 text-sm font-medium ${tab === id ? "border-b-2 border-slate-950 text-slate-950" : "text-slate-500 hover:text-slate-900"}`}
            >
              {label}
            </Link>
          ))}
        </div>

        {message && <p className="mb-4 text-sm text-slate-500">{message}</p>}

        {tab === "access" && settings && (
          <section className="max-w-2xl rounded-lg border border-slate-200 bg-white p-6">
            <div className="grid gap-4">
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Organization access</span>
                <select value={settings.accessMode} onChange={(e) => saveSettings({ accessMode: e.target.value as OrganizationSettings["accessMode"] })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm">
                  <option value="public">Public</option>
                  <option value="authenticated">Authenticated</option>
                  <option value="restricted">Restricted</option>
                </select>
              </label>
            </div>
          </section>
        )}

        {tab === "auth" && (
          <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
            <section className="rounded-lg border border-slate-200 bg-white p-6">
              <h2 className="mb-4 text-sm font-semibold text-slate-800">Configured login providers</h2>
              {providers.length === 0 ? (
                <p className="text-sm text-slate-500">No login providers configured.</p>
              ) : (
                <ul className="space-y-3">
                  {providers.map((provider) => (
                    <li key={provider.slug} className="rounded-md border border-slate-200 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-medium text-slate-950">{provider.displayName}</p>
                          <p className="text-xs text-slate-500">{provider.providerType} · {provider.enabled ? "enabled" : "disabled"}</p>
                          {provider.providerType === "github" && (
                            <div className="mt-3 rounded-md bg-slate-50 p-3">
                              <CopyLine label="GitHub callback URL" value={provider.callbackUrl || callbackUrlFor(provider.slug)} />
                            </div>
                          )}
                          {!provider.secretConfigured && provider.providerType !== "trusted_header" && provider.providerType !== "trusted_headers" && provider.providerType !== "local" && (
                            <p className="mt-2 text-xs text-amber-700">Client secret not configured</p>
                          )}
                        </div>
                        <div className="flex shrink-0 items-center gap-3">
                          <button type="button" onClick={() => updateProvider(provider, { enabled: !provider.enabled })} className="text-sm text-slate-700 hover:underline">
                            {provider.enabled ? "Disable" : "Enable"}
                          </button>
                          {provider.providerType !== "local" && <a href={provider.loginUrl} className="text-sm text-slate-700 hover:underline">Test login</a>}
                          <button type="button" onClick={() => deleteProvider(provider)} className="text-sm text-red-600 hover:text-red-800">Delete</button>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <div className="rounded-lg border border-slate-200 bg-white p-6">
              <h2 className="mb-4 text-sm font-semibold text-slate-800">Add login provider</h2>
              {providerForm === null ? (
                <div className="space-y-2">
                  {(["github", "oidc", "trusted_header"] as const).map((type) => (
                    <button
                      key={type}
                      type="button"
                      onClick={() => setProviderForm(emptyProviderFor(type))}
                      className="w-full rounded-md border border-slate-200 px-4 py-3 text-left text-sm font-medium text-slate-800 hover:border-slate-400 hover:bg-slate-50"
                    >
                      {type === "github" && "Configure GitHub"}
                      {type === "oidc" && "Configure OIDC / SSO"}
                      {type === "trusted_header" && "Configure trusted proxy headers"}
                    </button>
                  ))}
                </div>
              ) : (
                <form onSubmit={saveProvider} className="space-y-4">
                  <Field label="Slug" value={providerForm.slug} onChange={(v) => setProviderForm((f) => f && ({ ...f, slug: v }))} />
                  <Field label="Display name" value={providerForm.displayName} onChange={(v) => setProviderForm((f) => f && ({ ...f, displayName: v }))} />
                  {providerForm.providerType === "github" && (
                    <GitHubSetupInstructions slug={providerForm.slug} publicBaseUrl={me.publicBaseUrl} />
                  )}
                  {(providerForm.providerType === "github" || providerForm.providerType === "oidc") && (
                    <>
                      <Field label="Client ID" value={providerForm.clientId} onChange={(v) => setProviderForm((f) => f && ({ ...f, clientId: v }))} />
                      <label className="block">
                        <span className="mb-1 block text-sm font-medium text-slate-700">Client secret</span>
                        <input
                          type="password"
                          autoComplete="off"
                          value={providerForm.clientSecret}
                          onChange={(e) => setProviderForm((f) => f && ({ ...f, clientSecret: e.target.value }))}
                          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                        />
                      </label>
                    </>
                  )}
                  {providerForm.providerType === "oidc" && (
                    <>
                      <Field label="Issuer URL" value={providerForm.issuerUrl} onChange={(v) => setProviderForm((f) => f && ({ ...f, issuerUrl: v }))} />
                      <Field label="Group claim" value={providerForm.groupClaim} onChange={(v) => setProviderForm((f) => f && ({ ...f, groupClaim: v }))} />
                    </>
                  )}
                  {providerForm.providerType === "oidc" && (
                    <Field label="Scopes" value={providerForm.scopes} onChange={(v) => setProviderForm((f) => f && ({ ...f, scopes: v }))} />
                  )}
                  <div className="flex gap-3 pt-1">
                    <button type="submit" className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">Save provider</button>
                    <button type="button" onClick={() => setProviderForm(null)} className="px-4 py-2 text-sm text-slate-600 hover:text-slate-900">Cancel</button>
                  </div>
                </form>
              )}
            </div>
          </div>
        )}

        {tab === "users" && (
          <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
            <section className="rounded-lg border border-slate-200 bg-white p-6">
              <h2 className="mb-4 text-sm font-semibold text-slate-800">Users</h2>
              <ul className="space-y-3">
                {users.map((user) => (
                  <li key={user.id} className="flex items-center justify-between rounded-md border border-slate-200 p-4">
                    <div>
                      <p className="font-medium text-slate-950">{user.displayName}</p>
                      <p className="text-xs text-slate-500">{user.email} · {user.provider}{user.mustChangePassword ? " · password change required" : ""}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <select
                        value={user.organizationRole}
                        onChange={(e) => updateUserRole(user, e.target.value as OrgUser["organizationRole"])}
                        className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-800"
                        aria-label={`Organization role for ${user.displayName}`}
                      >
                        <option value="viewer">Viewer</option>
                        <option value="marketplace_creator">Marketplace creator</option>
                        <option value="organization_admin">Organization admin</option>
                      </select>
                      {user.provider === "local" && (
                        <button type="button" onClick={async () => {
                          const res = await fetch(`/api/organization/users/${user.id}/reset-password`, { method: "POST" });
                          const data = await res.json();
                          setTempPassword(data.temporaryPassword);
                        }} className="text-sm text-slate-700 hover:underline">Reset</button>
                      )}
                      <button type="button" onClick={async () => {
                        await fetch(`/api/organization/users/${user.id}/${user.disabledAt ? "enable" : "disable"}`, { method: "POST" });
                        load();
                      }} className="text-sm text-slate-700 hover:underline">{user.disabledAt ? "Enable" : "Disable"}</button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
            <section className="rounded-lg border border-slate-200 bg-white p-6">
              <h2 className="mb-4 text-sm font-semibold text-slate-800">Create local user</h2>
              <div className="space-y-3">
                <Field label="Email" value={newUserEmail} onChange={setNewUserEmail} />
                <Field label="Display name" value={newUserName} onChange={setNewUserName} />
                <button type="button" onClick={async () => {
                  const res = await fetch("/api/organization/users", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email: newUserEmail, displayName: newUserName }),
                  });
                  if (res.ok) {
                    const data = await res.json();
                    setTempPassword(data.temporaryPassword);
                    setNewUserEmail("");
                    setNewUserName("");
                    load();
                  }
                }} className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">Create user</button>
                {tempPassword && <CopyLine label="Temporary password" value={tempPassword} />}
              </div>
            </section>
          </div>
        )}

        {tab === "tokens" && (
          <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
            <section className="rounded-lg border border-slate-200 bg-white p-6">
              <h2 className="mb-1 text-sm font-semibold text-slate-800">Global read tokens</h2>
              <p className="mb-4 text-xs text-slate-500">Global tokens grant read access to all workspace-visible marketplaces. Marketplace-scoped tokens live in each marketplace's Settings → Tokens page.</p>
              {tokens.filter((t) => !t.revokedAt).length === 0 ? (
                <p className="text-sm text-slate-500">No active tokens.</p>
              ) : (
                <ul className="space-y-2">
                  {tokens.filter((t) => !t.revokedAt).map((token) => (
                    <li key={token.id} className="flex items-center justify-between gap-3 rounded-md border border-slate-200 p-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-slate-950">{token.name}</p>
                        <p className="text-xs text-slate-500">
                          {token.marketplaceSlug ? `Scoped to ${token.marketplaceSlug}` : "All marketplaces"} · Created {new Date(token.createdAt * 1000).toLocaleDateString()}
                        </p>
                      </div>
                      <button type="button" onClick={() => revokeToken(token.id)} className="shrink-0 text-sm text-red-600 hover:text-red-800">
                        Revoke
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section className="rounded-lg border border-slate-200 bg-white p-6">
              <h2 className="mb-4 text-sm font-semibold text-slate-800">Create token</h2>
              <div className="space-y-3">
                <Field label="Token name" value={newTokenName} onChange={setNewTokenName} />
                <button type="button" onClick={createToken} className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">
                  Create token
                </button>
                {createdToken && <CopyLine label="Access token" value={createdToken} />}
              </div>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}

function callbackUrlFor(slug: string, publicBaseUrl = window.location.origin) {
  const cleanSlug = slug.trim() || "github";
  return `${publicBaseUrl.replace(/\/$/, "")}/auth/callback/${cleanSlug}`;
}

function GitHubSetupInstructions({ slug, publicBaseUrl }: { slug: string; publicBaseUrl: string }) {
  return (
    <div className="rounded-md border border-amber-200 bg-amber-50 p-4">
      <h3 className="text-sm font-semibold text-amber-950">Before saving GitHub</h3>
      <div className="mt-3 space-y-3 text-sm text-amber-950">
        <p>Create or edit the GitHub OAuth app, then set its Authorization callback URL to this exact value.</p>
        <CopyLine label="Authorization callback URL" value={callbackUrlFor(slug, publicBaseUrl)} />
        <p>Enter the OAuth app Client ID and Client Secret below. The secret is stored in SkillShelf's database.</p>
      </div>
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value?: string | null; onChange: (value: string) => void }) {
  const id = `org-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  return (
    <label htmlFor={id} className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700">{label}</span>
      <input id={id} value={value ?? ""} onChange={(e) => onChange(e.target.value)} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
    </label>
  );
}
