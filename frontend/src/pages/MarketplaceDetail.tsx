import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import CopyLine from "../components/CopyLine";

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

type Tab = "plugins" | "settings";

export default function MarketplaceDetail() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const [marketplace, setMarketplace] = useState<Marketplace | null>(null);
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [tab, setTab] = useState<Tab>("plugins");
  const [loading, setLoading] = useState(true);
  const [settingsForm, setSettingsForm] = useState({ displayName: "", ownerName: "", ownerEmail: "" });
  const [visibility, setVisibility] = useState<"workspace" | "restricted">("workspace");
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsMsg, setSettingsMsg] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [tokenName, setTokenName] = useState("Claude read access");
  const [createdToken, setCreatedToken] = useState("");

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
    setSettingsForm({ displayName: mkt.displayName, ownerName: mkt.ownerName, ownerEmail: mkt.ownerEmail });
    setVisibility(mkt.visibility);
    setLoading(false);
  };

  useEffect(() => { load(); }, [slug]);

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

  if (loading) return <div className="p-8 text-sm text-slate-500">Loading...</div>;
  if (!marketplace) return null;

  const connectSnippet = `/plugin marketplace add ${window.location.origin}/m/${slug}`;
  const codexRepoUrl = `${window.location.origin}/m/${slug}/git/repo.git`;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-4">
          <Link to="/manage" className="text-sm text-slate-500 hover:text-slate-900">Marketplaces</Link>
          <span className="text-slate-300">/</span>
          <h1 className="text-lg font-semibold text-slate-950">{marketplace.displayName}</h1>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6">
        <div className="mb-6 space-y-3 rounded-lg border border-slate-200 bg-white px-4 py-3">
          <CopyLine label="Add to Claude Code" value={connectSnippet} />
          <CopyLine label="Codex-compatible git repo" value={codexRepoUrl} />
        </div>

        <div className="mb-6 flex gap-6 border-b border-slate-200">
          {(["plugins", "settings"] as Tab[]).map((item) => (
            <button
              key={item}
              onClick={() => setTab(item)}
              className={`pb-2 text-sm font-medium capitalize ${
                tab === item ? "border-b-2 border-slate-950 text-slate-950" : "text-slate-500 hover:text-slate-900"
              }`}
            >
              {item}
            </button>
          ))}
        </div>

        {tab === "plugins" && (
          <div>
            <div className="mb-4 flex justify-end">
              <Link to={`/manage/marketplaces/${slug}/plugins/new`} className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">
                Add plugin
              </Link>
            </div>
            {plugins.length === 0 ? (
              <p className="py-12 text-center text-sm text-slate-500">
                No plugins yet. <Link to={`/manage/marketplaces/${slug}/plugins/new`} className="font-medium text-slate-950 hover:underline">Create one</Link>.
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
                        <p className="mt-2 text-xs text-slate-500">
                          {plugin.skillCount} skills · {plugin.hookCount} hooks · {plugin.agentCount} agents · {plugin.mcpServerCount} MCP · {plugin.commandCount} commands · {plugin.monitorCount} monitors{plugin.hasSettings ? " · settings" : ""}
                        </p>
                      </div>
                      <div className="flex shrink-0 gap-3">
                        <Link to={`/manage/marketplaces/${slug}/plugins/${plugin.slug}/edit`} className="text-sm text-slate-700 hover:underline">Edit</Link>
                        <button onClick={() => handleDeletePlugin(plugin.slug)} className="text-sm text-red-600 hover:text-red-800">Delete</button>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {tab === "settings" && (
          <div className="max-w-lg space-y-8">
            <form onSubmit={handleSaveSettings} className="space-y-4 rounded-lg border border-slate-200 bg-white p-6">
              <h2 className="text-sm font-semibold text-slate-700">Marketplace details</h2>
              <SettingsField label="Name" value={settingsForm.displayName} onChange={(v) => setSettingsForm((f) => ({ ...f, displayName: v }))} />
              <SettingsField label="Owner name" value={settingsForm.ownerName} onChange={(v) => setSettingsForm((f) => ({ ...f, ownerName: v }))} />
              <SettingsField label="Owner email" type="email" value={settingsForm.ownerEmail} onChange={(v) => setSettingsForm((f) => ({ ...f, ownerEmail: v }))} />
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Visibility</span>
                <select
                  value={visibility}
                  onChange={(e) => setVisibility(e.target.value as "workspace" | "restricted")}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-200"
                >
                  <option value="workspace">Workspace</option>
                  <option value="restricted">Restricted</option>
                </select>
              </label>
              <div className="flex items-center gap-3">
                <button type="submit" disabled={settingsSaving} className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50">
                  {settingsSaving ? "Saving..." : "Save"}
                </button>
                {settingsMsg && <span className="text-sm text-slate-500">{settingsMsg}</span>}
              </div>
            </form>

            <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-6">
              <h2 className="text-sm font-semibold text-slate-700">Agent read token</h2>
              <SettingsField label="Token name" value={tokenName} onChange={setTokenName} />
              <button type="button" onClick={handleCreateToken} className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">
                Create token
              </button>
              {createdToken && (
                <CopyLine label="Read token" value={createdToken} />
              )}
            </div>

            <div className="rounded-lg border border-red-200 bg-white p-6">
              <h2 className="mb-2 text-sm font-semibold text-red-700">Danger zone</h2>
              <p className="mb-4 text-sm text-slate-600">Deleting this marketplace removes all plugins and the git repository permanently.</p>
              {deleteConfirm ? (
                <div className="flex gap-3">
                  <button onClick={handleDeleteMarketplace} className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700">Yes, delete permanently</button>
                  <button onClick={() => setDeleteConfirm(false)} className="px-4 py-2 text-sm text-slate-600 hover:text-slate-900">Cancel</button>
                </div>
              ) : (
                <button onClick={() => setDeleteConfirm(true)} className="rounded-md border border-red-400 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50">Delete marketplace</button>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
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
