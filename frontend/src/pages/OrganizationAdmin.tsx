import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import CopyLine from "../components/CopyLine";

interface CurrentUser {
  authenticated: boolean;
  organizationAdmin: boolean;
}

interface OrganizationSettings {
  accessMode: "public" | "authenticated" | "restricted";
  marketplaceCreation: "authenticated" | "organization_admin";
}

interface AuthProvider {
  slug: string;
  displayName: string;
  providerType: "local" | "github" | "oidc" | "trusted_header" | "trusted_headers";
  enabled: boolean;
  clientId: string;
  clientSecretEnvVar: string;
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
}

interface OrgUser {
  id: number;
  email: string;
  displayName: string;
  provider: string;
  disabledAt?: number | null;
  mustChangePassword: boolean;
}

type Tab = "access" | "auth" | "users" | "tokens";

const emptyProvider = {
  slug: "github",
  displayName: "GitHub",
  providerType: "github" as AuthProvider["providerType"],
  enabled: true,
  clientId: "",
  clientSecretEnvVar: "SKILLSHELF_GITHUB_CLIENT_SECRET",
  issuerUrl: "",
  authorizationUrl: "",
  tokenUrl: "",
  userinfoUrl: "",
  scopes: "read:user user:email",
  groupClaim: "",
  allowedOrgs: "",
};

export default function OrganizationAdmin() {
  const location = useLocation();
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [settings, setSettings] = useState<OrganizationSettings | null>(null);
  const [providers, setProviders] = useState<AuthProvider[]>([]);
  const [users, setUsers] = useState<OrgUser[]>([]);
  const [newUserEmail, setNewUserEmail] = useState("");
  const [newUserName, setNewUserName] = useState("");
  const [tempPassword, setTempPassword] = useState("");
  const [tab, setTab] = useState<Tab>(() => {
    if (location.pathname.endsWith("/auth")) return "auth";
    if (location.pathname.endsWith("/users")) return "users";
    if (location.pathname.endsWith("/tokens")) return "tokens";
    return "access";
  });
  const [message, setMessage] = useState("");
  const [providerForm, setProviderForm] = useState(emptyProvider);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const meRes = await fetch("/api/me");
    const meData = await meRes.json();
    setMe(meData);
    if (!meData.organizationAdmin) {
      setLoading(false);
      return;
    }
    const [settingsRes, providersRes, usersRes] = await Promise.all([
      fetch("/api/organization/settings"),
      fetch("/api/organization/auth-providers"),
      fetch("/api/organization/users"),
    ]);
    setSettings(await settingsRes.json());
    setProviders(providersRes.ok ? await providersRes.json() : []);
    setUsers(usersRes.ok ? await usersRes.json() : []);
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
    setMessage("");
    const r = await fetch("/api/organization/auth-providers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(providerForm),
    });
    setMessage(r.ok ? "Provider saved." : "Could not save provider.");
    if (r.ok) {
      setProviderForm(emptyProvider);
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

  return (
    <div>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <h1 className="mb-1 text-lg font-semibold text-slate-950">Organization settings</h1>
        <p className="mb-6 text-xs text-slate-500">Access, login, and tenant-wide controls</p>
        <div className="mb-6 flex gap-6 border-b border-slate-200">
          {(["access", "auth", "users", "tokens"] as Tab[]).map((item) => (
            <button
              key={item}
              onClick={() => setTab(item)}
              className={`pb-2 text-sm font-medium capitalize ${tab === item ? "border-b-2 border-slate-950 text-slate-950" : "text-slate-500 hover:text-slate-900"}`}
            >
              {item}
            </button>
          ))}
        </div>

        {message && <p className="mb-4 text-sm text-slate-500">{message}</p>}

        {tab === "access" && settings && (
          <section className="max-w-2xl rounded-lg border border-slate-200 bg-white p-6">
            <div className="grid gap-4 md:grid-cols-2">
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Organization access</span>
                <select value={settings.accessMode} onChange={(e) => saveSettings({ accessMode: e.target.value as OrganizationSettings["accessMode"] })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm">
                  <option value="public">Public</option>
                  <option value="authenticated">Authenticated</option>
                  <option value="restricted">Restricted</option>
                </select>
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Marketplace creation</span>
                  <select value={settings.marketplaceCreation} onChange={(e) => saveSettings({ marketplaceCreation: e.target.value as OrganizationSettings["marketplaceCreation"] })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm">
                  <option value="authenticated">Authenticated users</option>
                  <option value="organization_admin">Organization admins</option>
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
                          {!provider.secretConfigured && provider.providerType !== "trusted_header" && provider.providerType !== "trusted_headers" && provider.providerType !== "local" && (
                            <p className="mt-2 text-xs text-amber-700">Missing env var: {provider.clientSecretEnvVar}</p>
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

            <form onSubmit={saveProvider} className="rounded-lg border border-slate-200 bg-white p-6">
              <h2 className="mb-4 text-sm font-semibold text-slate-800">Add login provider</h2>
              <div className="space-y-4">
                <Field label="Slug" value={providerForm.slug} onChange={(v) => setProviderForm((f) => ({ ...f, slug: v }))} />
                <Field label="Display name" value={providerForm.displayName} onChange={(v) => setProviderForm((f) => ({ ...f, displayName: v }))} />
                <label className="block">
                  <span className="mb-1 block text-sm font-medium text-slate-700">Provider type</span>
                  <select value={providerForm.providerType} onChange={(e) => setProviderForm((f) => ({ ...f, providerType: e.target.value as AuthProvider["providerType"], scopes: e.target.value === "github" ? "read:user user:email" : "openid email profile" }))} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm">
                    <option value="github">GitHub</option>
                    <option value="oidc">Generic OIDC / SSO</option>
                    <option value="trusted_header">Trusted proxy headers</option>
                  </select>
                </label>
                <Field label="Client ID" value={providerForm.clientId} onChange={(v) => setProviderForm((f) => ({ ...f, clientId: v }))} />
                <Field label="Client secret env var" value={providerForm.clientSecretEnvVar} onChange={(v) => setProviderForm((f) => ({ ...f, clientSecretEnvVar: v }))} />
                {providerForm.providerType === "oidc" && (
                  <>
                    <Field label="Issuer URL" value={providerForm.issuerUrl} onChange={(v) => setProviderForm((f) => ({ ...f, issuerUrl: v }))} />
                    <Field label="Group claim" value={providerForm.groupClaim} onChange={(v) => setProviderForm((f) => ({ ...f, groupClaim: v }))} />
                  </>
                )}
                <Field label="Scopes" value={providerForm.scopes} onChange={(v) => setProviderForm((f) => ({ ...f, scopes: v }))} />
                <button className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">Save provider</button>
              </div>
            </form>
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
                    <div className="flex gap-3">
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
          <section className="max-w-2xl rounded-lg border border-slate-200 bg-white p-6">
            <h2 className="mb-3 text-sm font-semibold text-slate-800">Global read tokens</h2>
            <p className="mb-4 text-sm text-slate-500">Global tokens remain available through the API for organization admins. Marketplace-scoped read tokens live in each marketplace settings page.</p>
            <CopyLine label="Token API" value="/api/access-tokens" />
          </section>
        )}
      </main>
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
