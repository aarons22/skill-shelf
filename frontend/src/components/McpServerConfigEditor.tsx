import { Field, Select, StringListField, KeyValueField, KVPair, kvToRecord, recordToKv } from "./FormHelpers";

export type McpServerConfig =
  | { type: "stdio"; command: string; args: string[]; env: KVPair[] }
  | { type: "http"; url: string; headers: KVPair[] }
  | { type: "sse"; url: string; headers: KVPair[] };

const TYPE_OPTIONS = [
  { value: "stdio", label: "stdio (local process)" },
  { value: "http", label: "HTTP" },
  { value: "sse", label: "SSE" },
];

export function defaultMcpConfig(): McpServerConfig {
  return { type: "stdio", command: "", args: [], env: [] };
}

export function mcpConfigFromRaw(raw: Record<string, unknown>): McpServerConfig {
  const type = String(raw.type ?? "stdio");
  switch (type) {
    case "http":
      return { type: "http", url: String(raw.url ?? ""), headers: recordToKv((raw.headers ?? {}) as Record<string, string>) };
    case "sse":
      return { type: "sse", url: String(raw.url ?? ""), headers: recordToKv((raw.headers ?? {}) as Record<string, string>) };
    default:
      return {
        type: "stdio",
        command: String(raw.command ?? ""),
        args: Array.isArray(raw.args) ? (raw.args as string[]) : [],
        env: recordToKv((raw.env ?? {}) as Record<string, string>),
      };
  }
}

export function mcpConfigToPayload(c: McpServerConfig): Record<string, unknown> {
  switch (c.type) {
    case "stdio": {
      const out: Record<string, unknown> = { type: "stdio", command: c.command };
      if (c.args.length > 0) out.args = c.args;
      const env = kvToRecord(c.env);
      if (Object.keys(env).length > 0) out.env = env;
      return out;
    }
    case "http":
    case "sse": {
      const out: Record<string, unknown> = { type: c.type, url: c.url };
      const headers = kvToRecord(c.headers);
      if (Object.keys(headers).length > 0) out.headers = headers;
      return out;
    }
  }
}

export default function McpServerConfigEditor({ value, onChange }: { value: McpServerConfig; onChange: (next: McpServerConfig) => void }) {
  function setType(t: string) {
    switch (t) {
      case "http": onChange({ type: "http", url: "", headers: [] }); break;
      case "sse":  onChange({ type: "sse",  url: "", headers: [] }); break;
      default:     onChange({ type: "stdio", command: "", args: [], env: [] });
    }
  }

  return (
    <div className="md:col-span-2 space-y-4">
      <Select label="Connection type" value={value.type} options={TYPE_OPTIONS} onChange={setType} required />
      {value.type === "stdio" && (
        <>
          <Field label="Command" value={value.command} onChange={(v) => onChange({ ...value, command: v })} required />
          <StringListField label="Arguments" value={value.args} onChange={(v) => onChange({ ...value, args: v })} addLabel="Add argument" placeholder="argument" />
          <KeyValueField label="Environment variables" value={value.env} onChange={(v) => onChange({ ...value, env: v })} addLabel="Add variable" keyPlaceholder="NAME" valuePlaceholder="value" />
        </>
      )}
      {(value.type === "http" || value.type === "sse") && (
        <>
          <Field label="URL" value={value.url} onChange={(v) => onChange({ ...value, url: v })} required />
          <KeyValueField label="Headers" value={value.headers} onChange={(v) => onChange({ ...value, headers: v })} addLabel="Add header" keyPlaceholder="Header-Name" valuePlaceholder="value" />
        </>
      )}
    </div>
  );
}
