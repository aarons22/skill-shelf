import { Field, Select, NumberField, StringListField, KeyValueField, TextArea, KVPair, kvToRecord, recordToKv } from "./FormHelpers";

export type HookHandler =
  | { type: "command"; command: string; args: string[]; timeout: number | null }
  | { type: "http"; url: string; timeout: number | null }
  | { type: "mcp_tool"; server: string; tool: string; input: KVPair[] }
  | { type: "prompt"; prompt: string }
  | { type: "agent"; name: string };

const TYPE_OPTIONS = [
  { value: "command", label: "Shell command" },
  { value: "http", label: "HTTP webhook" },
  { value: "mcp_tool", label: "MCP tool" },
  { value: "prompt", label: "Prompt injection" },
  { value: "agent", label: "Sub-agent" },
];

export function defaultHookHandler(): HookHandler {
  return { type: "command", command: "", args: [], timeout: 30 };
}

export function hookHandlerFromRaw(raw: Record<string, unknown>): HookHandler {
  const type = String(raw.type ?? "command");
  switch (type) {
    case "http":
      return { type: "http", url: String(raw.url ?? ""), timeout: typeof raw.timeout === "number" ? raw.timeout : null };
    case "mcp_tool":
      return { type: "mcp_tool", server: String(raw.server ?? ""), tool: String(raw.tool ?? ""), input: recordToKv((raw.input ?? {}) as Record<string, string>) };
    case "prompt":
      return { type: "prompt", prompt: String(raw.prompt ?? "") };
    case "agent":
      return { type: "agent", name: String(raw.name ?? "") };
    default:
      return {
        type: "command",
        command: String(raw.command ?? ""),
        args: Array.isArray(raw.args) ? (raw.args as string[]) : [],
        timeout: typeof raw.timeout === "number" ? raw.timeout : null,
      };
  }
}

export function hookHandlerToPayload(h: HookHandler): Record<string, unknown> {
  switch (h.type) {
    case "command": {
      const out: Record<string, unknown> = { type: "command", command: h.command };
      if (h.args.length > 0) out.args = h.args;
      if (h.timeout !== null) out.timeout = h.timeout;
      return out;
    }
    case "http": {
      const out: Record<string, unknown> = { type: "http", url: h.url };
      if (h.timeout !== null) out.timeout = h.timeout;
      return out;
    }
    case "mcp_tool":
      return { type: "mcp_tool", server: h.server, tool: h.tool, input: kvToRecord(h.input) };
    case "prompt":
      return { type: "prompt", prompt: h.prompt };
    case "agent":
      return { type: "agent", name: h.name };
  }
}

export default function HookHandlerEditor({ value, onChange }: { value: HookHandler; onChange: (next: HookHandler) => void }) {
  function setType(t: string) {
    switch (t) {
      case "http":      onChange({ type: "http", url: "", timeout: null }); break;
      case "mcp_tool":  onChange({ type: "mcp_tool", server: "", tool: "", input: [] }); break;
      case "prompt":    onChange({ type: "prompt", prompt: "" }); break;
      case "agent":     onChange({ type: "agent", name: "" }); break;
      default:          onChange({ type: "command", command: "", args: [], timeout: null });
    }
  }

  return (
    <div className="md:col-span-2 space-y-4">
      <Select label="Handler type" value={value.type} options={TYPE_OPTIONS} onChange={setType} required />
      {value.type === "command" && (
        <>
          <Field label="Command" value={value.command} onChange={(v) => onChange({ ...value, command: v })} required />
          <StringListField label="Arguments" value={value.args} onChange={(v) => onChange({ ...value, args: v })} addLabel="Add argument" placeholder="argument" />
          <NumberField label="Timeout (seconds)" value={value.timeout} onChange={(v) => onChange({ ...value, timeout: v })} min={1} placeholder="30" />
        </>
      )}
      {value.type === "http" && (
        <>
          <Field label="URL" value={value.url} onChange={(v) => onChange({ ...value, url: v })} required />
          <NumberField label="Timeout (seconds)" value={value.timeout} onChange={(v) => onChange({ ...value, timeout: v })} min={1} placeholder="30" />
        </>
      )}
      {value.type === "mcp_tool" && (
        <>
          <Field label="MCP server name" value={value.server} onChange={(v) => onChange({ ...value, server: v })} required />
          <Field label="Tool name" value={value.tool} onChange={(v) => onChange({ ...value, tool: v })} required />
          <KeyValueField label="Tool input" value={value.input} onChange={(v) => onChange({ ...value, input: v })} addLabel="Add input field" keyPlaceholder="parameter name" valuePlaceholder="value" />
        </>
      )}
      {value.type === "prompt" && (
        <TextArea label="Prompt text" value={value.prompt} onChange={(v) => onChange({ ...value, prompt: v })} rows={5} />
      )}
      {value.type === "agent" && (
        <Field label="Agent name (slug)" value={value.name} onChange={(v) => onChange({ ...value, name: v })} required />
      )}
    </div>
  );
}
