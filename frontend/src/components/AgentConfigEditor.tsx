import { Select, NumberField } from "./FormHelpers";

export type AgentConfig = {
  model?: string;
  maxTurns?: number | null;
  [key: string]: unknown;
};

const MODEL_OPTIONS = [
  { value: "", label: "— inherit from user settings —" },
  { value: "claude-opus-4-7", label: "Claude Opus 4.7" },
  { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
  { value: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5" },
];

export function agentConfigFromRaw(raw: Record<string, unknown>): AgentConfig {
  return { ...raw };
}

export function agentConfigToPayload(c: AgentConfig): Record<string, unknown> {
  const out: Record<string, unknown> = { ...c };
  if (!out.model) delete out.model;
  if (out.maxTurns === null || out.maxTurns === undefined) delete out.maxTurns;
  return out;
}

export default function AgentConfigEditor({ value, onChange }: { value: AgentConfig; onChange: (next: AgentConfig) => void }) {
  const model = typeof value.model === "string" ? value.model : "";
  const maxTurns = typeof value.maxTurns === "number" ? value.maxTurns : null;

  return (
    <div className="md:col-span-2 grid gap-4 md:grid-cols-2">
      <Select
        label="Model"
        value={model}
        options={MODEL_OPTIONS}
        onChange={(v) => onChange({ ...value, model: v || undefined })}
      />
      <NumberField
        label="Max turns"
        value={maxTurns}
        onChange={(v) => onChange({ ...value, maxTurns: v })}
        min={1}
        placeholder="unlimited"
      />
    </div>
  );
}
