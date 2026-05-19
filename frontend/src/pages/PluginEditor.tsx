import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

interface Marketplace { slug: string; displayName: string }
interface Plugin { slug: string; displayName: string; description: string; version: string }
interface Item { slug: string; displayName: string; description?: string; event?: string; matcher?: string; command?: string }

const defaultAgentConfig = '{\n  "model": "sonnet",\n  "maxTurns": 10\n}';
const defaultMcpConfig = '{\n  "type": "http",\n  "url": "https://example.com/mcp"\n}';
const defaultSettings = '{\n  "agent": "reviewer"\n}';

export default function PluginEditor() {
  const { slug, pluginSlug } = useParams<{ slug: string; pluginSlug?: string }>();
  const navigate = useNavigate();
  const isEditing = Boolean(pluginSlug);
  const detailPath = useMemo(() => `/marketplace/${slug ?? ""}`, [slug]);
  const [marketplace, setMarketplace] = useState<Marketplace | null>(null);
  const [plugin, setPlugin] = useState<Plugin | null>(null);
  const [form, setForm] = useState({ displayName: "", description: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [items, setItems] = useState<Record<string, Item[]>>({});
  const [settingsText, setSettingsText] = useState(defaultSettings);
  const [component, setComponent] = useState({
    skillName: "", skillDescription: "", skillContent: "",
    hookName: "", hookEvent: "PostToolUse", hookMatcher: "Write|Edit", hookCommand: "${CLAUDE_PLUGIN_ROOT}/scripts/check.sh",
    agentName: "", agentDescription: "", agentPrompt: "", agentConfig: defaultAgentConfig,
    mcpName: "", mcpConfig: defaultMcpConfig,
    commandName: "", commandDescription: "", commandContent: "",
    monitorName: "", monitorCommand: "tail -F ./logs/error.log", monitorDescription: "", monitorWhen: "always",
  });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!slug) return;
      setLoading(true);
      setError("");
      const marketplaceRes = await fetch(`/api/marketplaces/${slug}`);
      if (!marketplaceRes.ok) {
        navigate("/");
        return;
      }
      const marketplaceData = await marketplaceRes.json();
      if (cancelled) return;
      setMarketplace(marketplaceData);
      if (isEditing && pluginSlug) {
        const pluginRes = await fetch(`/api/marketplaces/${slug}/plugins/${pluginSlug}`);
        if (!pluginRes.ok) {
          navigate(detailPath);
          return;
        }
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
    const paths = ["skills", "hooks", "agents", "mcp-servers", "commands", "monitors"];
    const results = await Promise.all(paths.map((path) => fetch(`/api/marketplaces/${slug}/plugins/${pluginSlug}/${path}`)));
    const next: Record<string, Item[]> = {};
    for (let i = 0; i < paths.length; i += 1) {
      next[paths[i]] = results[i].ok ? await results[i].json() : [];
    }
    setItems(next);
    const settings = await fetch(`/api/marketplaces/${slug}/plugins/${pluginSlug}/settings`);
    if (settings.ok) {
      const data = await settings.json();
      setSettingsText(JSON.stringify(data.settings ?? {}, null, 2));
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
    navigate(`/marketplace/${slug}/plugins/${data.slug}/edit`);
  };

  async function postComponent(path: string, body: object) {
    if (!slug || !pluginSlug) return;
    setError("");
    const res = await fetch(`/api/marketplaces/${slug}/plugins/${pluginSlug}/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      setError("Could not save that component. Check required fields and JSON.");
      return;
    }
    await loadComponents();
  }

  async function deleteComponent(path: string, itemSlug: string) {
    if (!slug || !pluginSlug || !confirm(`Delete "${itemSlug}"?`)) return;
    await fetch(`/api/marketplaces/${slug}/plugins/${pluginSlug}/${path}/${itemSlug}`, { method: "DELETE" });
    await loadComponents();
  }

  if (loading) return <div className="min-h-screen bg-slate-50 p-8 text-sm text-slate-500">Loading...</div>;
  if (!marketplace) return null;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-4">
          <Link to="/" className="text-sm text-slate-500 hover:text-slate-900">Marketplaces</Link>
          <span className="text-slate-300">/</span>
          <Link to={detailPath} className="text-sm text-slate-500 hover:text-slate-900">{marketplace.displayName}</Link>
          <span className="text-slate-300">/</span>
          <h1 className="text-lg font-semibold text-slate-950">{isEditing ? "Edit plugin" : "Add plugin"}</h1>
        </div>
      </header>
      <main className="mx-auto max-w-5xl space-y-6 px-4 py-8">
        <form onSubmit={savePlugin} className="rounded-lg border border-slate-200 bg-white p-6">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Plugin name" value={form.displayName} onChange={(value) => setForm((current) => ({ ...current, displayName: value }))} required />
            <Field label="Description" value={form.description} onChange={(value) => setForm((current) => ({ ...current, description: value }))} required />
          </div>
          <div className="mt-4 flex items-center gap-3">
            <button disabled={saving} className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50">{saving ? "Saving..." : "Save plugin"}</button>
            {plugin && <span className="font-mono text-xs text-slate-400">v{plugin.version} · {plugin.slug}</span>}
            {error && <span className="text-sm text-red-600">{error}</span>}
          </div>
        </form>

        {isEditing && pluginSlug && (
          <>
            <Warning />
            <ComponentPanel title="Skills" items={items.skills ?? []} onDelete={(item) => deleteComponent("skills", item)}>
              <Field label="Name" value={component.skillName} onChange={(v) => setComponent((c) => ({ ...c, skillName: v }))} />
              <Field label="Description" value={component.skillDescription} onChange={(v) => setComponent((c) => ({ ...c, skillDescription: v }))} />
              <TextArea label="Instructions" value={component.skillContent} onChange={(v) => setComponent((c) => ({ ...c, skillContent: v }))} />
              <Action onClick={() => postComponent("skills", { displayName: component.skillName, description: component.skillDescription, content: component.skillContent })}>Add skill</Action>
            </ComponentPanel>

            <ComponentPanel title="Hooks" items={items.hooks ?? []} onDelete={(item) => deleteComponent("hooks", item)}>
              <Field label="Name" value={component.hookName} onChange={(v) => setComponent((c) => ({ ...c, hookName: v }))} />
              <Field label="Event" value={component.hookEvent} onChange={(v) => setComponent((c) => ({ ...c, hookEvent: v }))} />
              <Field label="Matcher" value={component.hookMatcher} onChange={(v) => setComponent((c) => ({ ...c, hookMatcher: v }))} />
              <Field label="Command" value={component.hookCommand} onChange={(v) => setComponent((c) => ({ ...c, hookCommand: v }))} />
              <Action onClick={() => postComponent("hooks", { displayName: component.hookName, event: component.hookEvent, matcher: component.hookMatcher, handler: { type: "command", command: component.hookCommand, args: [], timeout: 30 }, unsafeConfirmed: true })}>Add hook</Action>
            </ComponentPanel>

            <ComponentPanel title="Agents" items={items.agents ?? []} onDelete={(item) => deleteComponent("agents", item)}>
              <Field label="Name" value={component.agentName} onChange={(v) => setComponent((c) => ({ ...c, agentName: v }))} />
              <Field label="Description" value={component.agentDescription} onChange={(v) => setComponent((c) => ({ ...c, agentDescription: v }))} />
              <TextArea label="Config JSON" value={component.agentConfig} onChange={(v) => setComponent((c) => ({ ...c, agentConfig: v }))} rows={5} />
              <TextArea label="Prompt" value={component.agentPrompt} onChange={(v) => setComponent((c) => ({ ...c, agentPrompt: v }))} />
              <Action onClick={() => postComponent("agents", { displayName: component.agentName, description: component.agentDescription, prompt: component.agentPrompt, config: JSON.parse(component.agentConfig || "{}") })}>Add agent</Action>
            </ComponentPanel>

            <ComponentPanel title="MCP servers" items={items["mcp-servers"] ?? []} onDelete={(item) => deleteComponent("mcp-servers", item)}>
              <Field label="Name" value={component.mcpName} onChange={(v) => setComponent((c) => ({ ...c, mcpName: v }))} />
              <TextArea label="Config JSON" value={component.mcpConfig} onChange={(v) => setComponent((c) => ({ ...c, mcpConfig: v }))} rows={6} />
              <Action onClick={() => postComponent("mcp-servers", { displayName: component.mcpName, config: JSON.parse(component.mcpConfig || "{}"), unsafeConfirmed: true })}>Add MCP server</Action>
            </ComponentPanel>

            <ComponentPanel title="Commands" items={items.commands ?? []} onDelete={(item) => deleteComponent("commands", item)}>
              <Field label="Name" value={component.commandName} onChange={(v) => setComponent((c) => ({ ...c, commandName: v }))} />
              <Field label="Description" value={component.commandDescription} onChange={(v) => setComponent((c) => ({ ...c, commandDescription: v }))} />
              <TextArea label="Content" value={component.commandContent} onChange={(v) => setComponent((c) => ({ ...c, commandContent: v }))} />
              <Action onClick={() => postComponent("commands", { displayName: component.commandName, description: component.commandDescription, content: component.commandContent })}>Add command</Action>
            </ComponentPanel>

            <ComponentPanel title="Monitors" items={items.monitors ?? []} onDelete={(item) => deleteComponent("monitors", item)}>
              <Field label="Name" value={component.monitorName} onChange={(v) => setComponent((c) => ({ ...c, monitorName: v }))} />
              <Field label="Command" value={component.monitorCommand} onChange={(v) => setComponent((c) => ({ ...c, monitorCommand: v }))} />
              <Field label="Description" value={component.monitorDescription} onChange={(v) => setComponent((c) => ({ ...c, monitorDescription: v }))} />
              <Field label="When" value={component.monitorWhen} onChange={(v) => setComponent((c) => ({ ...c, monitorWhen: v }))} />
              <Action onClick={() => postComponent("monitors", { displayName: component.monitorName, command: component.monitorCommand, description: component.monitorDescription, when: component.monitorWhen, unsafeConfirmed: true })}>Add monitor</Action>
            </ComponentPanel>

            <section className="rounded-lg border border-slate-200 bg-white p-6">
              <h2 className="mb-4 text-sm font-semibold text-slate-900">Default settings</h2>
              <TextArea label="settings.json" value={settingsText} onChange={setSettingsText} rows={6} />
              <Action onClick={() => postSettings(slug!, pluginSlug, settingsText, setError)}>Save settings</Action>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

async function postSettings(slug: string, pluginSlug: string, value: string, setError: (value: string) => void) {
  setError("");
  const res = await fetch(`/api/marketplaces/${slug}/plugins/${pluginSlug}/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ settings: JSON.parse(value || "{}") }),
  });
  if (!res.ok) setError("Could not save settings JSON.");
}

function Warning() {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      Hooks, MCP servers, and monitors can execute commands on users' machines after installation. Only add components your team trusts.
    </div>
  );
}

function ComponentPanel({ title, items, onDelete, children }: { title: string; items: Item[]; onDelete: (slug: string) => void; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
        <span className="text-xs text-slate-400">{items.length}</span>
      </div>
      {items.length > 0 && (
        <ul className="mb-5 divide-y divide-slate-100 rounded-md border border-slate-200">
          {items.map((item) => (
            <li key={item.slug} className="flex items-center justify-between gap-3 px-3 py-2">
              <span className="min-w-0 truncate text-sm text-slate-700">{item.displayName} <span className="font-mono text-xs text-slate-400">({item.slug})</span></span>
              <button onClick={() => onDelete(item.slug)} className="text-xs font-medium text-red-600 hover:text-red-800">Delete</button>
            </li>
          ))}
        </ul>
      )}
      <div className="grid gap-4 md:grid-cols-2">{children}</div>
    </section>
  );
}

function Action({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return <button type="button" onClick={onClick} className="h-10 self-end rounded-md bg-slate-950 px-4 text-sm font-medium text-white hover:bg-slate-800">{children}</button>;
}

function Field({ label, value, onChange, required = false }: { label: string; value: string; onChange: (value: string) => void; required?: boolean }) {
  const id = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-700">{label}</label>
      <input id={id} required={required} value={value} onChange={(e) => onChange(e.target.value)} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-200" />
    </div>
  );
}

function TextArea({ label, value, onChange, rows = 8 }: { label: string; value: string; onChange: (value: string) => void; rows?: number }) {
  const id = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div className="md:col-span-2">
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-700">{label}</label>
      <textarea id={id} rows={rows} value={value} onChange={(e) => onChange(e.target.value)} className="w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm leading-6 focus:outline-none focus:ring-2 focus:ring-slate-200" />
    </div>
  );
}
