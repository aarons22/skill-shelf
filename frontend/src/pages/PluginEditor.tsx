import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { Field } from "../components/FormHelpers";
import PluginSettingsEditor from "../components/PluginSettingsEditor";
import { useMe } from "../lib/auth";

type ComponentType = "skills" | "hooks" | "agents" | "mcp-servers" | "monitors";
type EditorTab = ComponentType | "settings";

interface Marketplace { slug: string; displayName: string }
interface Plugin { slug: string; displayName: string; description: string; version: string }
interface Item { slug: string; displayName: string; description?: string }

const SINGULAR_LABELS: Record<ComponentType, string> = {
  skills: "skill", hooks: "hook", agents: "agent",
  "mcp-servers": "MCP server", monitors: "monitor",
};

const DOC_URLS: Record<ComponentType, string> = {
  skills: "https://docs.anthropic.com/en/docs/claude-code/skills",
  hooks: "https://docs.anthropic.com/en/docs/claude-code/hooks",
  agents: "https://docs.anthropic.com/en/docs/claude-code/sub-agents",
  "mcp-servers": "https://docs.anthropic.com/en/docs/claude-code/mcp",
  monitors: "https://code.claude.com/docs/en/monitoring-usage",
};

const SECTION_TITLES: Record<ComponentType, string> = {
  skills: "Skills", hooks: "Hooks", agents: "Agents",
  "mcp-servers": "MCP Servers", monitors: "Monitors",
};

const EDITOR_TABS: EditorTab[] = ["skills", "hooks", "agents", "mcp-servers", "monitors", "settings"];

function editorTabLabel(tab: EditorTab): string {
  if (tab === "settings") return "Settings";
  return SECTION_TITLES[tab];
}

const UNSAFE_TABS: EditorTab[] = ["hooks", "mcp-servers", "monitors"];

export default function PluginEditor() {
  const { slug, pluginSlug } = useParams<{ slug: string; pluginSlug?: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { me } = useMe();
  const isEditing = Boolean(pluginSlug);
  const detailPath = useMemo(() => `/manage/${slug ?? ""}`, [slug]);
  const [marketplace, setMarketplace] = useState<Marketplace | null>(null);
  const [plugin, setPlugin] = useState<Plugin | null>(null);
  const [form, setForm] = useState({ displayName: "", description: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [items, setItems] = useState<Record<string, Item[]>>({});
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [editorTab, setEditorTab] = useState<EditorTab>(() => {
    const stateTab = (location.state as { tab?: EditorTab } | null)?.tab;
    return stateTab && EDITOR_TABS.includes(stateTab) ? stateTab : "skills";
  });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!slug) return;
      setLoading(true);
      setError("");
      const marketplaceRes = await fetch(`/api/marketplaces/${slug}`);
      if (!marketplaceRes.ok) { navigate("/manage"); return; }
      const marketplaceData = await marketplaceRes.json();
      if (cancelled) return;
      setMarketplace(marketplaceData);
      if (isEditing && pluginSlug) {
        const pluginRes = await fetch(`/api/marketplaces/${slug}/plugins/${pluginSlug}`);
        if (!pluginRes.ok) { navigate(detailPath); return; }
        const pluginData = await pluginRes.json();
        setPlugin(pluginData);
        setForm({ displayName: pluginData.displayName, description: pluginData.description });
        await loadComponents();
      }
      setLoading(false);
    }
    load();
    return () => { cancelled = true; };
  }, [slug, pluginSlug, isEditing]);

  async function loadComponents() {
    if (!slug || !pluginSlug) return;
    const paths: ComponentType[] = ["skills", "hooks", "agents", "mcp-servers", "monitors"];
    const results = await Promise.all(paths.map((path) => fetch(`/api/marketplaces/${slug}/plugins/${pluginSlug}/${path}`)));
    const next: Record<string, Item[]> = {};
    for (let i = 0; i < paths.length; i += 1) {
      next[paths[i]] = results[i].ok ? await results[i].json() : [];
    }
    setItems(next);
    const settingsRes = await fetch(`/api/marketplaces/${slug}/plugins/${pluginSlug}/settings`);
    if (settingsRes.ok) {
      const data = await settingsRes.json();
      setSettings(data.settings ?? {});
    }
  }

  const savePlugin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!slug) return;
    setSaving(true);
    setError("");
    const res = await fetch(isEditing ? `/api/marketplaces/${slug}/plugins/${pluginSlug}` : `/api/marketplaces/${slug}/plugins`, {
      method: isEditing ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    setSaving(false);
    if (!res.ok) {
      setError(res.status === 409 ? "A plugin with that name already exists." : "Failed to save plugin.");
      return;
    }
    const data = await res.json();
    navigate(`/manage/${slug}/plugins/${data.slug}/edit`);
  };

  async function deleteComponent(path: string, itemSlug: string) {
    if (!slug || !pluginSlug || !confirm(`Delete "${itemSlug}"?`)) return;
    await fetch(`/api/marketplaces/${slug}/plugins/${pluginSlug}/${path}/${itemSlug}`, { method: "DELETE" });
    await loadComponents();
  }

  const canDeleteContent = Boolean(
    slug && me && (me.organizationAdmin || me.marketplaceAdminSlugs.includes(slug) || me.marketplaceMaintainerSlugs.includes(slug)),
  );

  if (loading) return <div className="min-h-screen bg-slate-50 p-8 text-sm text-slate-500">Loading...</div>;
  if (!marketplace) return null;

  return (
    <div>
      <main className="mx-auto max-w-5xl space-y-6 px-4 py-6">
        <nav className="flex items-center gap-2 text-sm">
          <Link to="/manage" className="text-slate-500 hover:text-slate-900">Marketplaces</Link>
          <span className="text-slate-300">/</span>
          <Link to={detailPath} className="text-slate-500 hover:text-slate-900">{marketplace.displayName}</Link>
          <span className="text-slate-300">/</span>
          <span className="font-medium text-slate-950">{isEditing ? "Edit plugin" : "Add plugin"}</span>
        </nav>
        <form onSubmit={savePlugin} className="rounded-lg border border-slate-200 bg-white p-6">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Plugin name" value={form.displayName} onChange={(value) => setForm((c) => ({ ...c, displayName: value }))} required />
            <Field label="Description" value={form.description} onChange={(value) => setForm((c) => ({ ...c, description: value }))} required />
          </div>
          <div className="mt-4 flex items-center gap-3">
            <button disabled={saving} className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50">{saving ? "Saving..." : "Save plugin"}</button>
            {plugin && <span className="font-mono text-xs text-slate-400">v{plugin.version} · {plugin.slug}</span>}
            {error && <span className="text-sm text-red-600">{error}</span>}
          </div>
        </form>

        {isEditing && pluginSlug && (
          <>
            <div className="flex gap-1 border-b border-slate-200">
              {EDITOR_TABS.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setEditorTab(t)}
                  className={`px-4 py-2 text-sm font-medium transition-colors ${
                    editorTab === t
                      ? "border-b-2 border-slate-950 text-slate-950"
                      : "text-slate-500 hover:text-slate-900"
                  }`}
                >
                  {editorTabLabel(t)}
                  {t !== "settings" && (items[t] ?? []).length > 0 && (
                    <span className="ml-1.5 rounded-full bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-500">
                      {(items[t] ?? []).length}
                    </span>
                  )}
                </button>
              ))}
            </div>

            {UNSAFE_TABS.includes(editorTab) && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                {editorTab === "hooks" && "Hooks run shell commands on users' machines after tool use. Only add hooks your team trusts."}
                {editorTab === "mcp-servers" && "MCP servers run processes on users' machines. Only add servers your team trusts."}
                {editorTab === "monitors" && "Monitors run shell commands in the background on users' machines. Only add monitors your team trusts."}
              </div>
            )}

            {editorTab !== "settings" ? (
              <ComponentPanel
                title={SECTION_TITLES[editorTab as ComponentType]}
                items={items[editorTab] ?? []}
                path={editorTab as ComponentType}
                docUrl={DOC_URLS[editorTab as ComponentType]}
                onAdd={() => navigate(`/manage/${slug}/plugins/${pluginSlug}/${editorTab}/new`)}
                onDelete={(item) => deleteComponent(editorTab as ComponentType, item)}
                slug={slug!}
                pluginSlug={pluginSlug}
                canDelete={canDeleteContent}
              />
            ) : (
              <section className="rounded-lg border border-slate-200 bg-white p-6">
                <PluginSettingsEditor value={settings} onChange={setSettings} />
                <button type="button" onClick={() => saveSettings(slug!, pluginSlug, settings, setError)} className="mt-4 rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">
                  Save settings
                </button>
                {error && <span className="mt-2 block text-sm text-red-600">{error}</span>}
              </section>
            )}

          </>
        )}
      </main>
    </div>
  );
}

async function saveSettings(slug: string, pluginSlug: string, value: Record<string, unknown>, setError: (v: string) => void) {
  setError("");
  const res = await fetch(`/api/marketplaces/${slug}/plugins/${pluginSlug}/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ settings: value }),
  });
  if (!res.ok) setError("Could not save settings.");
}

function ComponentPanel({ title, items, path, docUrl, onAdd, onDelete, slug, pluginSlug, canDelete }: {
  title: string; items: Item[]; path: string; docUrl: string;
  onAdd: () => void; onDelete: (slug: string) => void;
  slug: string; pluginSlug: string;
  canDelete: boolean;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-500">{items.length}</span>
          <a href={docUrl} target="_blank" rel="noopener noreferrer" title={`${title} documentation`} className="text-xs text-slate-400 hover:text-slate-700">↗</a>
        </div>
        <button type="button" onClick={onAdd} className="shrink-0 rounded-md bg-slate-950 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800">
          Add {SINGULAR_LABELS[path as ComponentType]}
        </button>
      </div>
      {items.length > 0 && (
        <ul className="divide-y divide-slate-100 rounded-md border border-slate-200">
          {items.map((item) => (
            <li key={item.slug} className="flex items-center justify-between gap-3 px-3 py-2">
              <span className="min-w-0 truncate text-sm text-slate-700">
                {item.displayName} <span className="font-mono text-xs text-slate-400">({item.slug})</span>
              </span>
              <div className="flex shrink-0 items-center gap-3">
                <Link
                  to={`/manage/${slug}/plugins/${pluginSlug}/${path}/${item.slug}/edit`}
                  className="text-xs font-medium text-slate-600 hover:text-slate-900"
                >
                  Edit
                </Link>
                {canDelete && (
                  <button type="button" onClick={() => onDelete(item.slug)} className="text-xs font-medium text-red-600 hover:text-red-800">
                    Delete
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

