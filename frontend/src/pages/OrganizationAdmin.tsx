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

interface AuditEvent {
  id: number;
  actorUserId?: number | null;
  actorDisplayName?: string | null;
  actorEmail?: string | null;
  action: string;
  targetType: string;
  targetId: string;
  metadata: Record<string, unknown>;
  createdAt: number;
}

type Tab = "access" | "auth" | "users" | "audit";

interface OidcPreset {
  id: string;
  label: string;
  displayName: string;
  domainLabel: string | null;
  domainPlaceholder: string;
  deriveIssuer: (domain: string) => string;
  steps: () => string[];
}

const OIDC_PRESETS: OidcPreset[] = [
  {
    id: "auth0",
    label: "Auth0",
    displayName: "Auth0",
    domainLabel: "Auth0 Domain",
    domainPlaceholder: "your-tenant.us.auth0.com",
    deriveIssuer: (d) => `https://${d.replace(/^https?:\/\//, "").replace(/\/$/, "")}/`,
    steps: () => [
      "Go to Auth0 → Applications → Create Application → Regular Web App.",
      "Set Allowed Callback URLs to the callback URL shown above.",
      "Copy the Client ID and Client Secret into the fields below.",
    ],
  },
  {
    id: "okta",
    label: "Okta",
    displayName: "Okta",
    domainLabel: "Okta domain",
    domainPlaceholder: "dev-12345.okta.com",
    deriveIssuer: (d) => `https://${d.replace(/^https?:\/\//, "").replace(/\/$/, "")}`,
    steps: () => [
      "Go to Okta Admin → Applications → Create App Integration → OIDC – Web Application.",
      "Set Sign-in redirect URI to the callback URL shown above.",
      "Copy the Client ID and Client Secret into the fields below.",
    ],
  },
  {
    id: "entra",
    label: "Microsoft Entra ID",
    displayName: "Microsoft Entra ID",
    domainLabel: "Tenant ID",
    domainPlaceholder: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    deriveIssuer: (t) => `https://login.microsoftonline.com/${t.trim()}/v2.0`,
    steps: () => [
      "Go to Entra → App registrations → New registration.",
      "Add a Redirect URI (Web) set to the callback URL shown above.",
      "Go to Certificates & secrets → New client secret.",
      "Copy the Application (client) ID and secret value into the fields below.",
    ],
  },
  {
    id: "google",
    label: "Google Workspace",
    displayName: "Google Workspace",
    domainLabel: null,
    domainPlaceholder: "",
    deriveIssuer: () => "https://accounts.google.com",
    steps: () => [
      "Go to Google Cloud Console → APIs & Services → Credentials → Create OAuth client ID → Web application.",
      "Add an Authorized redirect URI set to the callback URL shown above.",
      "Copy the Client ID and Client Secret into the fields below.",
    ],
  },
  {
    id: "oidc",
    label: "Custom OIDC",
    displayName: "SSO",
    domainLabel: "Issuer URL",
    domainPlaceholder: "https://idp.example.com/",
    deriveIssuer: (v) => v,
    steps: () => [
      "Your IdP must publish a discovery document at /.well-known/openid-configuration.",
      "Register this application with your IdP and set the redirect URI to the callback URL shown above.",
      "Copy the Client ID and Client Secret into the fields below.",
    ],
  },
];

interface ProviderFormState {
  preset: string;
  domainValue: string;
  slug: string;
  displayName: string;
  providerType: "github" | "oidc" | "trusted_header";
  enabled: boolean;
  clientId: string;
  clientSecret: string;
  issuerUrl: string;
  authorizationUrl: string;
  tokenUrl: string;
  userinfoUrl: string;
  scopes: string;
  groupClaim: string;
  allowedOrgs: string;
  advancedOpen: boolean;
  groupClaimEnabled: boolean;
  endpointOverrideEnabled: boolean;
}

function emptyFormFor(type: "github" | "oidc-preset" | "trusted_header", presetId?: string): ProviderFormState {
  const base: Omit<ProviderFormState, "preset" | "slug" | "displayName" | "providerType"> = {
    domainValue: "", enabled: true, clientId: "", clientSecret: "", issuerUrl: "",
    authorizationUrl: "", tokenUrl: "", userinfoUrl: "", scopes: "", groupClaim: "",
    allowedOrgs: "", advancedOpen: false, groupClaimEnabled: false, endpointOverrideEnabled: false,
  };
  if (type === "github") return { ...base, preset: "github", slug: "github", displayName: "GitHub", providerType: "github" };
  if (type === "trusted_header") return { ...base, preset: "trusted_header", slug: "trusted-header", displayName: "Trusted proxy", providerType: "trusted_header" };
  const preset = OIDC_PRESETS.find((p) => p.id === presetId) ?? OIDC_PRESETS[OIDC_PRESETS.length - 1];
  return { ...base, preset: preset.id, slug: preset.id, displayName: preset.displayName, providerType: "oidc", scopes: "openid email profile" };
}

export default function OrganizationAdmin() {
  const location = useLocation();
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [settings, setSettings] = useState<OrganizationSettings | null>(null);
  const [providers, setProviders] = useState<AuthProvider[]>([]);
  const [users, setUsers] = useState<OrgUser[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [auditAction, setAuditAction] = useState("");
  const [auditTargetType, setAuditTargetType] = useState("");
  const [newUserEmail, setNewUserEmail] = useState("");
  const [newUserName, setNewUserName] = useState("");
  const [tempPassword, setTempPassword] = useState("");
  const [message, setMessage] = useState("");
  const [providerForm, setProviderForm] = useState<ProviderFormState | null>(null);
  const [saveError, setSaveError] = useState("");
  const [loading, setLoading] = useState(true);

  const tab: Tab = (() => {
    if (location.pathname.endsWith("/auth")) return "auth";
    if (location.pathname.endsWith("/users")) return "users";
    if (location.pathname.endsWith("/audit")) return "audit";
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

  const loadAudit = async () => {
    const params = new URLSearchParams({ limit: "50" });
    if (auditAction.trim()) params.set("action", auditAction.trim());
    if (auditTargetType.trim()) params.set("targetType", auditTargetType.trim());
    const res = await fetch(`/api/audit-events?${params.toString()}`);
    setAuditEvents(res.ok ? await res.json() : []);
  };

  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (me?.organizationAdmin && tab === "audit") {
      loadAudit();
    }
  }, [me?.organizationAdmin, tab, auditAction, auditTargetType]);

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
    setSaveError("");
    setMessage("");

    let issuerUrl = providerForm.issuerUrl;
    if (providerForm.providerType === "oidc") {
      const preset = OIDC_PRESETS.find((p) => p.id === providerForm.preset);
      issuerUrl = preset ? preset.deriveIssuer(providerForm.domainValue) : providerForm.domainValue;
    }

    const { preset: _preset, domainValue: _dv, advancedOpen: _ao, groupClaimEnabled, endpointOverrideEnabled, ...rest } = providerForm;
    const payload = {
      ...rest,
      issuerUrl,
      groupClaim: groupClaimEnabled ? rest.groupClaim : "",
      authorizationUrl: endpointOverrideEnabled ? rest.authorizationUrl : "",
      tokenUrl: endpointOverrideEnabled ? rest.tokenUrl : "",
      userinfoUrl: endpointOverrideEnabled ? rest.userinfoUrl : "",
    };

    const r = await fetch("/api/organization/auth-providers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (r.ok) {
      setProviderForm(null);
      load();
    } else {
      const data = await r.json().catch(() => ({}));
      setSaveError(data.detail || "Could not save provider.");
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
    { id: "audit", label: "Audit", path: "/organization/audit" },
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
                  <button
                    type="button"
                    onClick={() => setProviderForm(emptyFormFor("github"))}
                    className="w-full rounded-md border border-slate-200 px-4 py-3 text-left text-sm font-medium text-slate-800 hover:border-slate-400 hover:bg-slate-50"
                  >
                    Configure GitHub
                  </button>
                  {OIDC_PRESETS.map((preset) => (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => { setSaveError(""); setProviderForm(emptyFormFor("oidc-preset", preset.id)); }}
                      className="w-full rounded-md border border-slate-200 px-4 py-3 text-left text-sm font-medium text-slate-800 hover:border-slate-400 hover:bg-slate-50"
                    >
                      Configure {preset.label}
                    </button>
                  ))}
                  <button
                    type="button"
                    onClick={() => setProviderForm(emptyFormFor("trusted_header"))}
                    className="w-full rounded-md border border-slate-200 px-4 py-3 text-left text-sm font-medium text-slate-800 hover:border-slate-400 hover:bg-slate-50"
                  >
                    Configure trusted proxy headers
                  </button>
                </div>
              ) : (
                <form onSubmit={saveProvider} className="space-y-4">
                  {providerForm.providerType === "github" && (
                    <GitHubSetupInstructions slug={providerForm.slug} publicBaseUrl={me.publicBaseUrl} />
                  )}
                  {providerForm.providerType === "oidc" && (() => {
                    const preset = OIDC_PRESETS.find((p) => p.id === providerForm.preset) ?? OIDC_PRESETS[OIDC_PRESETS.length - 1];
                    return <OidcSetupInstructions preset={preset} slug={providerForm.slug} publicBaseUrl={me.publicBaseUrl} />;
                  })()}
                  <Field label="Display name" value={providerForm.displayName} onChange={(v) => setProviderForm((f) => f && ({ ...f, displayName: v }))} />
                  {providerForm.providerType === "oidc" && (() => {
                    const preset = OIDC_PRESETS.find((p) => p.id === providerForm.preset) ?? OIDC_PRESETS[OIDC_PRESETS.length - 1];
                    return preset.domainLabel ? (
                      <Field label={preset.domainLabel} placeholder={preset.domainPlaceholder} value={providerForm.domainValue} onChange={(v) => setProviderForm((f) => f && ({ ...f, domainValue: v }))} />
                    ) : null;
                  })()}
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
                  {providerForm.providerType !== "trusted_header" && (
                    <AdvancedDisclosure open={providerForm.advancedOpen} onToggle={() => setProviderForm((f) => f && ({ ...f, advancedOpen: !f.advancedOpen }))}>
                      <Field label="Slug" value={providerForm.slug} onChange={(v) => setProviderForm((f) => f && ({ ...f, slug: v }))} />
                      {providerForm.providerType === "oidc" && (
                        <Field label="Scopes" value={providerForm.scopes} onChange={(v) => setProviderForm((f) => f && ({ ...f, scopes: v }))} />
                      )}
                      {providerForm.providerType === "oidc" && (
                        <>
                          <label className="flex cursor-pointer items-center gap-2 text-sm">
                            <input type="checkbox" checked={providerForm.groupClaimEnabled} onChange={(e) => setProviderForm((f) => f && ({ ...f, groupClaimEnabled: e.target.checked }))} />
                            <span className="font-medium text-slate-700">Restrict access by group</span>
                          </label>
                          {providerForm.groupClaimEnabled && (
                            <Field label="Group claim" value={providerForm.groupClaim} onChange={(v) => setProviderForm((f) => f && ({ ...f, groupClaim: v }))} />
                          )}
                          <label className="flex cursor-pointer items-center gap-2 text-sm">
                            <input type="checkbox" checked={providerForm.endpointOverrideEnabled} onChange={(e) => setProviderForm((f) => f && ({ ...f, endpointOverrideEnabled: e.target.checked }))} />
                            <span className="font-medium text-slate-700">Override endpoints manually</span>
                          </label>
                          {providerForm.endpointOverrideEnabled && (
                            <>
                              <Field label="Authorization URL" value={providerForm.authorizationUrl} onChange={(v) => setProviderForm((f) => f && ({ ...f, authorizationUrl: v }))} />
                              <Field label="Token URL" value={providerForm.tokenUrl} onChange={(v) => setProviderForm((f) => f && ({ ...f, tokenUrl: v }))} />
                              <Field label="Userinfo URL" value={providerForm.userinfoUrl} onChange={(v) => setProviderForm((f) => f && ({ ...f, userinfoUrl: v }))} />
                            </>
                          )}
                        </>
                      )}
                      {providerForm.providerType === "github" && (
                        <Field label="Allowed orgs (comma-separated)" value={providerForm.allowedOrgs} onChange={(v) => setProviderForm((f) => f && ({ ...f, allowedOrgs: v }))} />
                      )}
                    </AdvancedDisclosure>
                  )}
                  {saveError && <p className="text-sm text-red-600">{saveError}</p>}
                  <div className="flex gap-3 pt-1">
                    <button type="submit" className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">Save provider</button>
                    <button type="button" onClick={() => { setProviderForm(null); setSaveError(""); }} className="px-4 py-2 text-sm text-slate-600 hover:text-slate-900">Cancel</button>
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

        {tab === "audit" && (
          <section className="rounded-lg border border-slate-200 bg-white p-6">
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end">
              <Field label="Action" value={auditAction} onChange={setAuditAction} />
              <Field label="Target type" value={auditTargetType} onChange={setAuditTargetType} />
              <button type="button" onClick={() => { setAuditAction(""); setAuditTargetType(""); }} className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">
                Clear
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="py-2 pr-4 font-medium">Time</th>
                    <th className="py-2 pr-4 font-medium">Actor</th>
                    <th className="py-2 pr-4 font-medium">Action</th>
                    <th className="py-2 pr-4 font-medium">Target</th>
                    <th className="py-2 font-medium">Metadata</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {auditEvents.map((event) => (
                    <tr key={event.id}>
                      <td className="whitespace-nowrap py-3 pr-4 text-slate-600">{new Date(event.createdAt * 1000).toLocaleString()}</td>
                      <td className="py-3 pr-4">
                        <p className="font-medium text-slate-900">{event.actorDisplayName || "System"}</p>
                        {event.actorEmail && <p className="text-xs text-slate-500">{event.actorEmail}</p>}
                      </td>
                      <td className="whitespace-nowrap py-3 pr-4 font-mono text-xs text-slate-800">{event.action}</td>
                      <td className="whitespace-nowrap py-3 pr-4 text-slate-700">{event.targetType}:{event.targetId}</td>
                      <td className="max-w-md py-3 font-mono text-xs text-slate-500">{JSON.stringify(event.metadata)}</td>
                    </tr>
                  ))}
                  {auditEvents.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-6 text-center text-sm text-slate-500">No audit events found.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
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

function OidcSetupInstructions({ preset, slug, publicBaseUrl }: { preset: OidcPreset; slug: string; publicBaseUrl: string }) {
  const callbackUrl = callbackUrlFor(slug || preset.id, publicBaseUrl);
  const steps = preset.steps();
  return (
    <div className="rounded-md border border-amber-200 bg-amber-50 p-4">
      <h3 className="text-sm font-semibold text-amber-950">Before saving {preset.label}</h3>
      <div className="mt-3">
        <CopyLine label="Callback URL" value={callbackUrl} />
      </div>
      <ol className="mt-3 list-inside list-decimal space-y-1.5 text-sm text-amber-900">
        {steps.map((step, i) => <li key={i}>{step}</li>)}
      </ol>
    </div>
  );
}

function AdvancedDisclosure({ open, onToggle, children }: { open: boolean; onToggle: () => void; children: React.ReactNode }) {
  return (
    <div>
      <button type="button" onClick={onToggle} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800">
        <span className={`inline-block text-xs transition-transform ${open ? "rotate-90" : ""}`}>▶</span>
        Advanced
      </button>
      {open && <div className="mt-3 space-y-4 border-l border-slate-200 pl-4">{children}</div>}
    </div>
  );
}

function Field({ label, placeholder, value, onChange }: { label: string; placeholder?: string; value?: string | null; onChange: (value: string) => void }) {
  const id = `org-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  return (
    <label htmlFor={id} className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700">{label}</span>
      <input id={id} value={value ?? ""} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm placeholder:text-slate-400" />
    </label>
  );
}
