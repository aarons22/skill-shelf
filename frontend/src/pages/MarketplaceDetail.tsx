import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import CopyLine from "../components/CopyLine";
import { useMe } from "../lib/auth";

interface Marketplace {
  slug: string;
  displayName: string;
  ownerName: string;
  ownerEmail: string;
  visibility: "workspace" | "restricted";
  pluginCount?: number;
}

interface Plugin {
  slug: string;
  displayName: string;
  description: string;
  version: string;
  skillCount: number;
  hookCount: number;
  agentCount: number;
  mcpServerCount: number;
  commandCount: number;
  monitorCount: number;
  hasSettings: boolean;
}

interface MarketplaceUser {
  id: number;
  email: string;
  displayName: string;
  provider: string;
  marketplaceRole: "none" | "read" | "write" | "maintain" | "admin";
  isOwner: boolean;
}

type Tab = "plugins" | "details" | "people" | "tokens" | "danger";
const ALL_TABS: readonly Tab[] = ["plugins", "details", "people", "tokens", "danger"] as const;
const ADMIN_TABS: readonly Tab[] = ["details", "people", "tokens", "danger"] as const;

export default function MarketplaceDetail() {
  const { slug, tab: tabParam } = useParams<{ slug: string; tab?: string }>();
  const navigate = useNavigate();
  const { me } = useMe();
  const [marketplace, setMarketplace] = useState<Marketplace | null>(null);
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [users, setUsers] = useState<MarketplaceUser[]>([]);
  const tab: Tab = (ALL_TABS as readonly string[]).includes(tabParam ?? "")
    ? (tabParam as Tab)
    : "plugins";
  const [loading, setLoading] = useState(true);
  const [settingsForm, setSettingsForm] = useState({ displayName: "" });
  const [visibility, setVisibility] = useState<"workspace" | "restricted">("workspace");
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsMsg, setSettingsMsg] = useState("");
  const [deleteSlugInput, setDeleteSlugInput] = useState("");

  const [tokenName, setTokenName] = useState("Claude read access");
  const [createdToken, setCreatedToken] = useState("");
  const [userSearch, setUserSearch] = useState("");
  const [userSearchResults, setUserSearchResults] = useState<MarketplaceUser[]>([]);
  const [userSearchLoading, setUserSearchLoading] = useState(false);
  const [newUserRole, setNewUserRole] = useState<MarketplaceUser["marketplaceRole"]>("write");

  const load = async () => {
    setLoading(true);
    const [mktRes, pluginsRes] = await Promise.all([
      fetch(`/api/marketplaces/${slug}`),
      fetch(`/api/marketplaces/${slug}/plugins`),
    ]);
    if (!mktRes.ok) {
      navigate("/manage");
      return;
    }
    const mkt = await mktRes.json();
    setMarketplace(mkt);
    setPlugins(pluginsRes.ok ? await pluginsRes.json() : []);
    const usersRes = await fetch(`/api/marketplaces/${slug}/users`);
    setUsers(usersRes.ok ? await usersRes.json() : []);
    setSettingsForm({ displayName: mkt.displayName });
    setVisibility(mkt.visibility);
    setLoading(false);
  };

  useEffect(() => { load(); }, [slug]);

  const isMarketplaceAdmin = Boolean(
    marketplace && me && (me.organizationAdmin || me.marketplaceAdminSlugs.includes(marketplace.slug)),
  );
  const canDeleteContent = Boolean(
    marketplace && me && (isMarketplaceAdmin || me.marketplaceMaintainerSlugs.includes(marketplace.slug)),
  );

  useEffect(() => {
    if (ADMIN_TABS.includes(tab) && marketplace && !isMarketplaceAdmin) {
      navigate(`/manage/${marketplace.slug}`, { replace: true });
    }
  }, [tab, marketplace, isMarketplaceAdmin, navigate]);

  useEffect(() => {
    const query = userSearch.trim();
    if (!slug || query.length === 0) {
      setUserSearchResults([]);
      setUserSearchLoading(false);
      return;
    }
    setUserSearchLoading(true);
    const timer = window.setTimeout(async () => {
      const res = await fetch(`/api/marketplaces/${slug}/user-search?q=${encodeURIComponent(query)}`);
      setUserSearchResults(res.ok ? await res.json() : []);
      setUserSearchLoading(false);
    }, 150);
    return () => window.clearTimeout(timer);
  }, [slug, userSearch]);

  const handleDeletePlugin = async (pluginSlug: string) => {
    if (!confirm(`Delete plugin "${pluginSlug}"?`)) return;
    await fetch(`/api/marketplaces/${slug}/plugins/${pluginSlug}`, { method: "DELETE" });
    load();
  };

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setSettingsSaving(true);
    setSettingsMsg("");
    const r = await fetch(`/api/marketplaces/${slug}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...settingsForm, visibility }),
    });
    setSettingsSaving(false);
    setSettingsMsg(r.ok ? "Saved." : "Save failed.");
    if (r.ok) load();
  };

  const handleDeleteMarketplace = async () => {
    await fetch(`/api/marketplaces/${slug}`, { method: "DELETE" });
    navigate("/manage");
  };

  const handleCreateToken = async () => {
    setCreatedToken("");
    const r = await fetch("/api/access-tokens", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: tokenName, marketplaceSlug: slug }),
    });
    if (r.ok) {
      const data = await r.json();
      setCreatedToken(data.token);
    }
  };

  const handleUpdateUserRole = async (user: MarketplaceUser, marketplaceRole: MarketplaceUser["marketplaceRole"]) => {
    setSettingsMsg("");
    const r = await fetch(`/api/marketplaces/${slug}/users/${user.id}/role`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ marketplaceRole }),
    });
    setSettingsMsg(r.ok ? "User access updated." : "Could not update user access.");
    if (r.ok) load();
  };

  const handleAddUser = async (user: MarketplaceUser) => {
    await handleUpdateUserRole(user, newUserRole);
    setUserSearch("");
    setUserSearchResults([]);
    setNewUserRole("write");
  };

  if (loading) return <div className="p-8 text-sm text-slate-500">Loading...</div>;
  if (!marketplace) return null;

  return (
    <div>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <nav className="mb-4 flex items-center gap-2 text-sm">
          <Link to="/manage" className="text-slate-500 hover:text-slate-900">Marketplaces</Link>
          <span className="text-slate-300">/</span>
          <span className="font-medium text-slate-950">{marketplace.displayName}</span>
        </nav>

        <div className="mb-6 flex gap-6 border-b border-slate-200">
          {(["plugins", ...(isMarketplaceAdmin ? ADMIN_TABS : [])] as Tab[]).map((item) => (
            <Link
              key={item}
              to={item === "plugins" ? `/manage/${slug}` : `/manage/${slug}/${item}`}
              className={`pb-2 text-sm font-medium capitalize ${
                tab === item ? "border-b-2 border-slate-950 text-slate-950" : "text-slate-500 hover:text-slate-900"
              }`}
            >
              {item}
            </Link>
          ))}
        </div>

        {tab === "plugins" && (
          <div>
            <div className="mb-4 flex justify-end">
              <Link to={`/manage/${slug}/plugins/new`} className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">
                Add plugin
              </Link>
            </div>
            {plugins.length === 0 ? (
              <p className="py-12 text-center text-sm text-slate-500">
                No plugins yet. <Link to={`/manage/${slug}/plugins/new`} className="font-medium text-slate-950 hover:underline">Create one</Link>.
              </p>
            ) : (
              <ul className="space-y-3">
                {plugins.map((plugin) => (
                  <li key={plugin.slug} className="rounded-lg border border-slate-200 bg-white px-5 py-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-slate-950">{plugin.displayName}</p>
                        <p className="mt-0.5 truncate text-sm text-slate-500">{plugin.description}</p>
                        <p className="mt-2 font-mono text-xs text-slate-400">v{plugin.version} · {plugin.slug}</p>
                        <p className="mt-2 text-xs text-slate-500">{componentSummary(plugin)}</p>
                      </div>
                      <div className="flex shrink-0 gap-3">
                        <Link to={`/manage/${slug}/plugins/${plugin.slug}/edit`} className="text-sm text-slate-700 hover:underline">Edit</Link>
                        {canDeleteContent && (
                          <button onClick={() => handleDeletePlugin(plugin.slug)} className="text-sm text-red-600 hover:text-red-800">Delete</button>
                        )}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {tab === "details" && (
              <form onSubmit={handleSaveSettings} className="max-w-lg space-y-4 rounded-lg border border-slate-200 bg-white p-6">
                <h2 className="text-sm font-semibold text-slate-700">Marketplace details</h2>
                <SettingsField label="Name" value={settingsForm.displayName} onChange={(v) => setSettingsForm((f) => ({ ...f, displayName: v }))} />
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">Visibility</label>
                  <select
                    value={visibility}
                    onChange={(e) => setVisibility(e.target.value as "workspace" | "restricted")}
                    className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-200"
                  >
                    <option value="workspace">Workspace — visible to all signed-in users</option>
                    <option value="restricted">Restricted — requires explicit grant to read</option>
                  </select>
                </div>
                <div className="flex items-center gap-3">
                  <button type="submit" disabled={settingsSaving} className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50">
                    {settingsSaving ? "Saving..." : "Save"}
                  </button>
                  {settingsMsg && <span className="text-sm text-slate-500">{settingsMsg}</span>}
                </div>
              </form>
            )}

            {tab === "people" && (
              <div className="max-w-lg space-y-4 rounded-lg border border-slate-200 bg-white p-6">
                <h2 className="text-sm font-semibold text-slate-700">People</h2>
                <div className="space-y-3 rounded-md border border-slate-200 p-3">
                  <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
                    <SettingsField label="Search users" value={userSearch} onChange={setUserSearch} />
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-slate-700">Role</span>
                      <select
                        value={newUserRole}
                        onChange={(e) => setNewUserRole(e.target.value as MarketplaceUser["marketplaceRole"])}
                        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-200"
                      >
                        <option value="write">Write</option>
                        <option value="maintain">Maintain</option>
                        <option value="admin">Admin</option>
                      </select>
                    </label>
                  </div>
                  {userSearch.trim() && (
                    <div className="overflow-hidden rounded-md border border-slate-200">
                      {userSearchLoading ? (
                        <p className="px-3 py-2 text-sm text-slate-500">Searching…</p>
                      ) : userSearchResults.length === 0 ? (
                        <p className="px-3 py-2 text-sm text-slate-500">No matching users not already assigned.</p>
                      ) : (
                        userSearchResults.map((user) => (
                          <button
                            key={user.id}
                            type="button"
                            onClick={() => handleAddUser(user)}
                            className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-slate-50"
                          >
                            <span className="min-w-0">
                              <span className="block truncate font-medium text-slate-900">{user.displayName}</span>
                              <span className="block truncate text-xs text-slate-500">{user.email}</span>
                            </span>
                            <span className="text-xs font-medium text-slate-600">Add</span>
                          </button>
                        ))
                      )}
                    </div>
                  )}
                </div>
                {users.length === 0 ? (
                  <p className="text-sm text-slate-500">No marketplace people have been assigned yet.</p>
                ) : (
                  <ul className="space-y-3">
                    {users.map((user) => (
                      <li key={user.id} className="flex items-center justify-between gap-4 rounded-md border border-slate-200 p-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-slate-950">{user.displayName}</p>
                          <p className="truncate text-xs text-slate-500">{user.email} · {user.provider}{user.isOwner ? " · owner" : ""}</p>
                        </div>
                        {user.isOwner ? (
                          <span className="shrink-0 rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5 text-sm text-slate-700">Owner</span>
                        ) : (
                          <div className="flex shrink-0 items-center gap-2">
                            <select
                              value={user.marketplaceRole}
                              onChange={(e) => handleUpdateUserRole(user, e.target.value as MarketplaceUser["marketplaceRole"])}
                              className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-800"
                              aria-label={`Marketplace role for ${user.displayName}`}
                            >
                              <option value="read">Read</option>
                              <option value="write">Write</option>
                              <option value="maintain">Maintain</option>
                              <option value="admin">Admin</option>
                            </select>
                            <button
                              type="button"
                              onClick={() => handleUpdateUserRole(user, "none")}
                              className="rounded-md border border-red-300 px-2 py-1.5 text-sm text-red-600 hover:bg-red-50"
                            >
                              Remove
                            </button>
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {tab === "tokens" && (
              <div className="max-w-lg space-y-4 rounded-lg border border-slate-200 bg-white p-6">
                <div>
                  <h2 className="text-sm font-semibold text-slate-700">Read-only access token</h2>
                  <p className="mt-0.5 text-xs text-slate-500">Generated tokens let agents clone this marketplace without a user account.</p>
                </div>
                <SettingsField label="Token name" value={tokenName} onChange={setTokenName} />
                <button type="button" onClick={handleCreateToken} className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">
                  Create token
                </button>
                {createdToken && (
                  <CopyLine label="Read token" value={createdToken} />
                )}
              </div>
            )}

            {tab === "danger" && (
              <div className="max-w-lg rounded-lg border border-red-200 bg-white p-6">
                <h2 className="mb-2 text-sm font-semibold text-red-700">Delete marketplace</h2>
                <p className="mb-4 text-sm text-slate-600">This removes all plugins and the git repository permanently. This cannot be undone.</p>
                <p className="mb-2 text-sm font-medium text-slate-700">
                  Type <span className="font-mono font-semibold">{marketplace.slug}</span> to confirm
                </p>
                <div className="flex gap-2">
                  <input
                    value={deleteSlugInput}
                    onChange={(e) => setDeleteSlugInput(e.target.value)}
                    placeholder={marketplace.slug}
                    className="w-48 rounded-md border border-slate-300 px-3 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-red-200"
                  />
                  <button
                    onClick={handleDeleteMarketplace}
                    disabled={deleteSlugInput !== marketplace.slug}
                    className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Delete marketplace
                  </button>
                </div>
              </div>
            )}
      </main>
    </div>
  );
}



function componentSummary(p: Plugin): string {
  const parts: string[] = [];
  if (p.skillCount) parts.push(`${p.skillCount} skill${p.skillCount !== 1 ? "s" : ""}`);
  if (p.hookCount) parts.push(`${p.hookCount} hook${p.hookCount !== 1 ? "s" : ""}`);
  if (p.agentCount) parts.push(`${p.agentCount} agent${p.agentCount !== 1 ? "s" : ""}`);
  if (p.mcpServerCount) parts.push(`${p.mcpServerCount} MCP server${p.mcpServerCount !== 1 ? "s" : ""}`);
  if (p.commandCount) parts.push(`${p.commandCount} command${p.commandCount !== 1 ? "s" : ""}`);
  if (p.monitorCount) parts.push(`${p.monitorCount} monitor${p.monitorCount !== 1 ? "s" : ""}`);
  if (p.hasSettings) parts.push("settings");
  return parts.length ? parts.join(" · ") : "No components";
}

function SettingsField({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (v: string) => void; type?: string }) {
  const inputId = `settings-${label.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <div>
      <label htmlFor={inputId} className="mb-1 block text-sm font-medium text-slate-700">{label}</label>
      <input id={inputId} type={type} value={value} onChange={(e) => onChange(e.target.value)} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-200" />
    </div>
  );
}
