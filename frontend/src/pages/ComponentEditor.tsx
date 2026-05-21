import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Field, TextArea } from "../components/FormHelpers";
import HookHandlerEditor, { HookHandler, defaultHookHandler, hookHandlerFromRaw, hookHandlerToPayload } from "../components/HookHandlerEditor";
import McpServerConfigEditor, { McpServerConfig, defaultMcpConfig, mcpConfigFromRaw, mcpConfigToPayload } from "../components/McpServerConfigEditor";
import AgentConfigEditor, { AgentConfig, agentConfigFromRaw, agentConfigToPayload } from "../components/AgentConfigEditor";

type ComponentType = "skills" | "hooks" | "agents" | "mcp-servers" | "monitors";

const VALID_TYPES: ComponentType[] = ["skills", "hooks", "agents", "mcp-servers", "monitors"];
const SECTION_LABELS: Record<ComponentType, string> = {
  skills: "Skills", hooks: "Hooks", agents: "Agents",
  "mcp-servers": "MCP Servers", monitors: "Monitors",
};
const SINGULAR_LABELS: Record<ComponentType, string> = {
  skills: "skill", hooks: "hook", agents: "agent",
  "mcp-servers": "MCP server", monitors: "monitor",
};

type FormState =
  | { type: "skills"; displayName: string; description: string; content: string }
  | { type: "hooks"; displayName: string; event: string; matcher: string; handler: HookHandler }
  | { type: "agents"; displayName: string; description: string; prompt: string; config: AgentConfig }
  | { type: "mcp-servers"; displayName: string; config: McpServerConfig }
  | { type: "monitors"; displayName: string; command: string; description: string; when: string };

function mapToFormState(type: ComponentType, raw: Record<string, unknown>): FormState {
  switch (type) {
    case "skills":
      return { type, displayName: String(raw.displayName ?? ""), description: String(raw.description ?? ""), content: String(raw.content ?? "") };
    case "hooks":
      return { type, displayName: String(raw.displayName ?? ""), event: String(raw.event ?? ""), matcher: String(raw.matcher ?? ""), handler: hookHandlerFromRaw((raw.handler ?? {}) as Record<string, unknown>) };
    case "agents":
      return { type, displayName: String(raw.displayName ?? ""), description: String(raw.description ?? ""), prompt: String(raw.prompt ?? ""), config: agentConfigFromRaw((raw.config ?? {}) as Record<string, unknown>) };
    case "mcp-servers":
      return { type, displayName: String(raw.displayName ?? ""), config: mcpConfigFromRaw((raw.config ?? {}) as Record<string, unknown>) };
    case "monitors":
      return { type, displayName: String(raw.displayName ?? ""), command: String(raw.command ?? ""), description: String(raw.description ?? ""), when: String(raw.when ?? "") };
  }
}

function emptyFormState(type: ComponentType): FormState {
  switch (type) {
    case "skills": return { type, displayName: "", description: "", content: "" };
    case "hooks": return { type, displayName: "", event: "PostToolUse", matcher: "Write|Edit", handler: defaultHookHandler() };
    case "agents": return { type, displayName: "", description: "", prompt: "", config: agentConfigFromRaw({}) };
    case "mcp-servers": return { type, displayName: "", config: defaultMcpConfig() };
    case "monitors": return { type, displayName: "", command: "tail -F ./logs/error.log", description: "", when: "always" };
  }
}

function buildPayload(state: FormState): object {
  switch (state.type) {
    case "skills":
      return { displayName: state.displayName, description: state.description, content: state.content };
    case "hooks":
      return { displayName: state.displayName, event: state.event, matcher: state.matcher, handler: hookHandlerToPayload(state.handler), unsafeConfirmed: true };
    case "agents":
      return { displayName: state.displayName, description: state.description, prompt: state.prompt, config: agentConfigToPayload(state.config) };
    case "mcp-servers":
      return { displayName: state.displayName, config: mcpConfigToPayload(state.config), unsafeConfirmed: true };
    case "monitors":
      return { displayName: state.displayName, command: state.command, description: state.description, ...(state.when ? { when: state.when } : {}), unsafeConfirmed: true };
  }
}

export default function ComponentEditor() {
  const { slug, pluginSlug, componentType, componentSlug } = useParams<{
    slug: string; pluginSlug: string; componentType: string; componentSlug?: string;
  }>();
  const navigate = useNavigate();
  const isNew = !componentSlug;
  const pluginPath = `/manage/marketplaces/${slug}/plugins/${pluginSlug}/edit`;

  const [marketplace, setMarketplace] = useState<{ slug: string; displayName: string } | null>(null);
  const [plugin, setPlugin] = useState<{ slug: string; displayName: string } | null>(null);
  const [formState, setFormState] = useState<FormState | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!VALID_TYPES.includes(componentType as ComponentType)) {
      navigate(pluginPath);
      return;
    }
    async function load() {
      const [mktRes, plugRes] = await Promise.all([
        fetch(`/api/marketplaces/${slug}`),
        fetch(`/api/marketplaces/${slug}/plugins/${pluginSlug}`),
      ]);
      if (!mktRes.ok) { navigate("/manage"); return; }
      if (!plugRes.ok) { navigate(`/manage/marketplaces/${slug}`); return; }
      const [mkt, plug] = await Promise.all([mktRes.json(), plugRes.json()]);
      setMarketplace(mkt);
      setPlugin(plug);
      if (isNew) {
        setFormState(emptyFormState(componentType as ComponentType));
      } else {
        const compRes = await fetch(`/api/marketplaces/${slug}/plugins/${pluginSlug}/${componentType}/${componentSlug}`);
        if (!compRes.ok) { navigate(pluginPath); return; }
        setFormState(mapToFormState(componentType as ComponentType, await compRes.json()));
      }
      setLoading(false);
    }
    load();
  }, [slug, pluginSlug, componentType, componentSlug]);

  const save = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formState) return;
    setSaving(true);
    setError("");
    const payload = buildPayload(formState);
    const url = isNew
      ? `/api/marketplaces/${slug}/plugins/${pluginSlug}/${componentType}`
      : `/api/marketplaces/${slug}/plugins/${pluginSlug}/${componentType}/${componentSlug}`;
    const res = await fetch(url, {
      method: isNew ? "POST" : "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setSaving(false);
    if (!res.ok) { setError("Failed to save. Check required fields."); return; }
    navigate(pluginPath, { state: { tab: componentType } });
  }, [formState, isNew, slug, pluginSlug, componentType, componentSlug, navigate, pluginPath]);

  if (loading) return <div className="min-h-screen bg-slate-50 p-8 text-sm text-slate-500">Loading...</div>;
  if (!marketplace || !plugin || !formState) return null;

  const type = componentType as ComponentType;
  const sectionLabel = SECTION_LABELS[type];

  return (
    <div>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <nav className="mb-4 flex flex-wrap items-center gap-2 text-sm">
          <Link to="/manage" className="text-slate-500 hover:text-slate-900">Marketplaces</Link>
          <span className="text-slate-300">/</span>
          <Link to={`/manage/marketplaces/${slug}`} className="text-slate-500 hover:text-slate-900">{marketplace.displayName}</Link>
          <span className="text-slate-300">/</span>
          <Link to={pluginPath} className="text-slate-500 hover:text-slate-900">{plugin.displayName}</Link>
          <span className="text-slate-300">/</span>
          <Link to={pluginPath} state={{ tab: componentType }} className="text-slate-500 hover:text-slate-900">{sectionLabel}</Link>
          <span className="text-slate-300">/</span>
          <span className="font-medium text-slate-950">
            {isNew ? `New ${SINGULAR_LABELS[type]}` : formState.displayName}
          </span>
        </nav>
        <form onSubmit={save} className="rounded-lg border border-slate-200 bg-white p-6">
          <div className="grid gap-4 md:grid-cols-2">
            {renderFields(formState, setFormState as (updater: (prev: FormState) => FormState) => void)}
          </div>
          <div className="mt-6 flex items-center gap-3">
            <button type="submit" disabled={saving} className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50">
              {saving ? "Saving..." : isNew ? `Add ${SINGULAR_LABELS[type]}` : "Save"}
            </button>
            <button type="button" onClick={() => navigate(pluginPath)} className="rounded-md border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
              Cancel
            </button>
            {error && <span className="text-sm text-red-600">{error}</span>}
          </div>
        </form>
      </main>
    </div>
  );
}

function renderFields(state: FormState, setState: (updater: (prev: FormState) => FormState) => void) {
  const set = (key: string, value: unknown) =>
    setState((prev) => ({ ...prev, [key]: value }) as FormState);

  switch (state.type) {
    case "skills":
      return (
        <>
          <Field label="Name" value={state.displayName} onChange={(v) => set("displayName", v)} required />
          <Field label="Description" value={state.description} onChange={(v) => set("description", v)} required />
          <TextArea label="Instructions" value={state.content} onChange={(v) => set("content", v)} rows={12} />
        </>
      );
    case "hooks":
      return (
        <>
          <Field label="Name" value={state.displayName} onChange={(v) => set("displayName", v)} required />
          <Field label="Event" value={state.event} onChange={(v) => set("event", v)} required />
          <Field label="Matcher" value={state.matcher} onChange={(v) => set("matcher", v)} />
          <HookHandlerEditor value={state.handler} onChange={(v) => set("handler", v)} />
        </>
      );
    case "agents":
      return (
        <>
          <Field label="Name" value={state.displayName} onChange={(v) => set("displayName", v)} required />
          <Field label="Description" value={state.description} onChange={(v) => set("description", v)} required />
          <AgentConfigEditor value={state.config} onChange={(v) => set("config", v)} />
          <TextArea label="Prompt" value={state.prompt} onChange={(v) => set("prompt", v)} rows={10} />
        </>
      );
    case "mcp-servers":
      return (
        <>
          <Field label="Name" value={state.displayName} onChange={(v) => set("displayName", v)} required />
          <McpServerConfigEditor value={state.config} onChange={(v) => set("config", v)} />
        </>
      );
    case "monitors":
      return (
        <>
          <Field label="Name" value={state.displayName} onChange={(v) => set("displayName", v)} required />
          <Field label="Shell command" value={state.command} onChange={(v) => set("command", v)} required />
          <Field label="Description" value={state.description} onChange={(v) => set("description", v)} required />
          <Field label="When (optional)" value={state.when} onChange={(v) => set("when", v)} />
        </>
      );
  }
}
