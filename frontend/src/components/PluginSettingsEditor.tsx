import { Select, StringListField, KeyValueField, KVPair, kvToRecord, recordToKv } from "./FormHelpers";

const MODEL_OPTIONS = [
  { value: "", label: "— inherit from user settings —" },
  { value: "claude-opus-4-7", label: "Claude Opus 4.7" },
  { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
  { value: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5" },
];

const DEFAULT_MODE_OPTIONS = [
  { value: "", label: "— inherit from user settings —" },
  { value: "allow", label: "Allow (no prompts)" },
  { value: "ask", label: "Ask (prompt on each action)" },
  { value: "deny", label: "Deny" },
  { value: "acceptEdits", label: "Accept edits" },
  { value: "bypassPermissions", label: "Bypass all permissions" },
];

type SettingsForm = {
  model: string;
  permissionsDefaultMode: string;
  permissionsAllow: string[];
  permissionsDeny: string[];
  env: KVPair[];
  _rest: Record<string, unknown>;
};

function fromRaw(raw: Record<string, unknown>): SettingsForm {
  const perms = (raw.permissions ?? {}) as Record<string, unknown>;
  const { model, permissions, env, ...rest } = raw;
  return {
    model: typeof model === "string" ? model : "",
    permissionsDefaultMode: typeof perms.defaultMode === "string" ? perms.defaultMode : "",
    permissionsAllow: Array.isArray(perms.allow) ? (perms.allow as string[]) : [],
    permissionsDeny: Array.isArray(perms.deny) ? (perms.deny as string[]) : [],
    env: recordToKv((env ?? {}) as Record<string, string>),
    _rest: rest,
  };
}

function toRaw(f: SettingsForm): Record<string, unknown> {
  const out: Record<string, unknown> = { ...f._rest };
  if (f.model) out.model = f.model;
  const perms: Record<string, unknown> = {};
  if (f.permissionsDefaultMode) perms.defaultMode = f.permissionsDefaultMode;
  if (f.permissionsAllow.length > 0) perms.allow = f.permissionsAllow;
  if (f.permissionsDeny.length > 0) perms.deny = f.permissionsDeny;
  if (Object.keys(perms).length > 0) out.permissions = perms;
  const env = kvToRecord(f.env);
  if (Object.keys(env).length > 0) out.env = env;
  return out;
}

export function settingsToPayload(raw: Record<string, unknown>): Record<string, unknown> {
  return toRaw(fromRaw(raw));
}

export default function PluginSettingsEditor({ value, onChange }: { value: Record<string, unknown>; onChange: (next: Record<string, unknown>) => void }) {
  const form = fromRaw(value);

  function update(patch: Partial<SettingsForm>) {
    const next = { ...form, ...patch };
    onChange(toRaw(next));
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Select
        label="Default model"
        value={form.model}
        options={MODEL_OPTIONS}
        onChange={(v) => update({ model: v })}
      />
      <Select
        label="Default permission mode"
        value={form.permissionsDefaultMode}
        options={DEFAULT_MODE_OPTIONS}
        onChange={(v) => update({ permissionsDefaultMode: v })}
      />
      <StringListField
        label="Permissions — allow list"
        value={form.permissionsAllow}
        onChange={(v) => update({ permissionsAllow: v })}
        addLabel="Add allow rule"
        placeholder="e.g. Bash(git *)"
      />
      <StringListField
        label="Permissions — deny list"
        value={form.permissionsDeny}
        onChange={(v) => update({ permissionsDeny: v })}
        addLabel="Add deny rule"
        placeholder="e.g. Bash(rm *)"
      />
      <KeyValueField
        label="Environment variables"
        value={form.env}
        onChange={(v) => update({ env: v })}
        addLabel="Add variable"
        keyPlaceholder="NAME"
        valuePlaceholder="value"
      />
    </div>
  );
}
