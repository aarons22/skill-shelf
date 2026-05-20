import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Modal from "../components/Modal";
import { Field, TextArea } from "../components/FormHelpers";
import HookHandlerEditor, { HookHandler, defaultHookHandler, hookHandlerToPayload } from "../components/HookHandlerEditor";
import McpServerConfigEditor, { McpServerConfig, defaultMcpConfig, mcpConfigToPayload } from "../components/McpServerConfigEditor";
import AgentConfigEditor, { AgentConfig, agentConfigToPayload } from "../components/AgentConfigEditor";
import PluginSettingsEditor from "../components/PluginSettingsEditor";

type ComponentType = "skills" | "hooks" | "agents" | "mcp-servers" | "monitors";

interface Marketplace { slug: string; displayName: string }
interface Plugin { slug: string; displayName: string; description: string; version: string }
interface Item { slug: string; displayName: string; description?: string }

const MODAL_TITLES: Record<ComponentType, string> = {
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

export default function PluginEditor() {
  const { slug, pluginSlug } = useParams<{ slug: string; pluginSlug?: string }>();
  const navigate = useNavigate();
  const isEditing = Boolean(pluginSlug);
  const detailPath = useMemo(() => `/manage/marketplaces/${slug ?? ""}`, [slug]);
  const [marketplace, setMarketplace] = useState<Marketplace | null>(null);
  const [plugin, setPlugin] = useState<Plugin | null>(null);
  const [form, setForm] = useState({ displayName: "", description: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [items, setItems] = useState<Record<string, Item[]>>({});
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [openModal, setOpenModal] = useState<ComponentType | null>(null);

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
    navigate(`/manage/marketplaces/${slug}/plugins/${data.slug}/edit`);
  };

  async function postComponent(path: ComponentType, body: object): Promise<boolean> {
    if (!slug || !pluginSlug) return false;
    setError("");
    const res = await fetch(`/api/marketplaces/${slug}/plugins/${pluginSlug}/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      setError("Could not save that component. Check required fields.");
      return false;
    }
    setOpenModal(null);
    await loadComponents();
    return true;
  }

  async function deleteComponent(path: string, itemSlug: string) {
    if (!slug || !pluginSlug || !confirm(`Delete "${itemSlug}"?`)) return;
    await fetch(`/api/marketplaces/${slug}/plugins/${pluginSlug}/${path}/${itemSlug}`, { method: "DELETE" });
    await loadComponents();
  }

  const handleCloseModal = useCallback(() => {
    setOpenModal(null);
    setError("");
  }, []);

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
            {error && !openModal && <span className="text-sm text-red-600">{error}</span>}
          </div>
        </form>

        {isEditing && pluginSlug && (
          <>
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              Hooks, MCP servers, and monitors can execute commands on users' machines after installation. Only add components your team trusts.
            </div>

            {(["skills", "hooks", "agents", "mcp-servers", "monitors"] as ComponentType[]).map((type) => (
              <ComponentPanel
                key={type}
                title={SECTION_TITLES[type]}
                items={items[type] ?? []}
                path={type}
                docUrl={DOC_URLS[type]}
                onAdd={() => setOpenModal(type)}
                onDelete={(item) => deleteComponent(type, item)}
                slug={slug!}
                pluginSlug={pluginSlug}
              />
            ))}

            <section className="rounded-lg border border-slate-200 bg-white p-6">
              <div className="mb-4 flex items-center gap-2">
                <h2 className="text-sm font-semibold text-slate-900">Default settings</h2>
              </div>
              <PluginSettingsEditor value={settings} onChange={setSettings} />
              <button type="button" onClick={() => saveSettings(slug!, pluginSlug, settings, setError)} className="mt-4 rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">
                Save settings
              </button>
              {error && !openModal && <span className="mt-2 block text-sm text-red-600">{error}</span>}
            </section>

            {openModal && (
              <Modal title={`Add ${MODAL_TITLES[openModal]}`} onClose={handleCloseModal}>
                <AddComponentModal
                  type={openModal}
                  onSave={(body) => postComponent(openModal, body)}
                  onClose={handleCloseModal}
                  error={error}
                />
              </Modal>
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

function ComponentPanel({ title, items, path, docUrl, onAdd, onDelete, slug, pluginSlug }: {
  title: string; items: Item[]; path: string; docUrl: string;
  onAdd: () => void; onDelete: (slug: string) => void;
  slug: string; pluginSlug: string;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-500">{items.length}</span>
          <a href={docUrl} target="_blank" rel="noopener noreferrer" title={`${title} documentation`} className="text-xs text-slate-400 hover:text-slate-700">↗</a>
        </div>
        <button type="button" onClick={onAdd} className="rounded-md bg-slate-950 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800">
          Add {MODAL_TITLES[path as ComponentType]}
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
                  to={`/manage/marketplaces/${slug}/plugins/${pluginSlug}/${path}/${item.slug}/edit`}
                  className="text-xs font-medium text-slate-600 hover:text-slate-900"
                >
                  Edit
                </Link>
                <button type="button" onClick={() => onDelete(item.slug)} className="text-xs font-medium text-red-600 hover:text-red-800">
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function AddComponentModal({ type, onSave, onClose, error }: {
  type: ComponentType;
  onSave: (body: object) => Promise<boolean>;
  onClose: () => void;
  error: string;
}) {
  switch (type) {
    case "skills":      return <AddSkillForm onSave={onSave} onClose={onClose} error={error} />;
    case "hooks":       return <AddHookForm onSave={onSave} onClose={onClose} error={error} />;
    case "agents":      return <AddAgentForm onSave={onSave} onClose={onClose} error={error} />;
    case "mcp-servers": return <AddMcpForm onSave={onSave} onClose={onClose} error={error} />;
    case "monitors":    return <AddMonitorForm onSave={onSave} onClose={onClose} error={error} />;
  }
}

type FormProps = { onSave: (body: object) => Promise<boolean>; onClose: () => void; error: string };

function ModalActions({ onClose, error, label = "Add" }: { onClose: () => void; error: string; label?: string }) {
  return (
    <div className="mt-5 flex items-center gap-3">
      <button type="submit" className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">{label}</button>
      <button type="button" onClick={onClose} className="rounded-md border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Cancel</button>
      {error && <span className="text-sm text-red-600">{error}</span>}
    </div>
  );
}

function AddSkillForm({ onSave, onClose, error }: FormProps) {
  const [f, setF] = useState({ displayName: "", description: "", content: "" });
  return (
    <form onSubmit={async (e) => { e.preventDefault(); await onSave({ displayName: f.displayName, description: f.description, content: f.content }); }}>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Name" value={f.displayName} onChange={(v) => setF((c) => ({ ...c, displayName: v }))} required />
        <Field label="Description" value={f.description} onChange={(v) => setF((c) => ({ ...c, description: v }))} required />
        <TextArea label="Instructions" value={f.content} onChange={(v) => setF((c) => ({ ...c, content: v }))} rows={8} />
      </div>
      <ModalActions onClose={onClose} error={error} label="Add skill" />
    </form>
  );
}

function AddHookForm({ onSave, onClose, error }: FormProps) {
  const [f, setF] = useState({ displayName: "", event: "PostToolUse", matcher: "Write|Edit", handler: defaultHookHandler() as HookHandler });
  return (
    <form onSubmit={async (e) => {
      e.preventDefault();
      await onSave({ displayName: f.displayName, event: f.event, matcher: f.matcher, handler: hookHandlerToPayload(f.handler), unsafeConfirmed: true });
    }}>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Name" value={f.displayName} onChange={(v) => setF((c) => ({ ...c, displayName: v }))} required />
        <Field label="Event" value={f.event} onChange={(v) => setF((c) => ({ ...c, event: v }))} required />
        <Field label="Matcher (regex)" value={f.matcher} onChange={(v) => setF((c) => ({ ...c, matcher: v }))} />
        <HookHandlerEditor value={f.handler} onChange={(v) => setF((c) => ({ ...c, handler: v }))} />
      </div>
      <ModalActions onClose={onClose} error={error} label="Add hook" />
    </form>
  );
}

function AddAgentForm({ onSave, onClose, error }: FormProps) {
  const [f, setF] = useState({ displayName: "", description: "", prompt: "", config: {} as AgentConfig });
  return (
    <form onSubmit={async (e) => {
      e.preventDefault();
      await onSave({ displayName: f.displayName, description: f.description, prompt: f.prompt, config: agentConfigToPayload(f.config) });
    }}>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Name" value={f.displayName} onChange={(v) => setF((c) => ({ ...c, displayName: v }))} required />
        <Field label="Description" value={f.description} onChange={(v) => setF((c) => ({ ...c, description: v }))} required />
        <AgentConfigEditor value={f.config} onChange={(v) => setF((c) => ({ ...c, config: v }))} />
        <TextArea label="Prompt" value={f.prompt} onChange={(v) => setF((c) => ({ ...c, prompt: v }))} rows={8} />
      </div>
      <ModalActions onClose={onClose} error={error} label="Add agent" />
    </form>
  );
}

function AddMcpForm({ onSave, onClose, error }: FormProps) {
  const [f, setF] = useState({ displayName: "", config: defaultMcpConfig() as McpServerConfig });
  return (
    <form onSubmit={async (e) => {
      e.preventDefault();
      await onSave({ displayName: f.displayName, config: mcpConfigToPayload(f.config), unsafeConfirmed: true });
    }}>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Name" value={f.displayName} onChange={(v) => setF((c) => ({ ...c, displayName: v }))} required />
        <McpServerConfigEditor value={f.config} onChange={(v) => setF((c) => ({ ...c, config: v }))} />
      </div>
      <ModalActions onClose={onClose} error={error} label="Add MCP server" />
    </form>
  );
}

function AddMonitorForm({ onSave, onClose, error }: FormProps) {
  const [f, setF] = useState({ displayName: "", command: "tail -F ./logs/error.log", description: "", when: "always" });
  return (
    <form onSubmit={async (e) => {
      e.preventDefault();
      await onSave({ displayName: f.displayName, command: f.command, description: f.description, ...(f.when ? { when: f.when } : {}), unsafeConfirmed: true });
    }}>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Name" value={f.displayName} onChange={(v) => setF((c) => ({ ...c, displayName: v }))} required />
        <Field label="Shell command" value={f.command} onChange={(v) => setF((c) => ({ ...c, command: v }))} required />
        <Field label="Description" value={f.description} onChange={(v) => setF((c) => ({ ...c, description: v }))} required />
        <Field label="When (optional)" value={f.when} onChange={(v) => setF((c) => ({ ...c, when: v }))} />
      </div>
      <ModalActions onClose={onClose} error={error} label="Add monitor" />
    </form>
  );
}

