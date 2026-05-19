export function Field({ label, value, onChange, required = false }: { label: string; value: string; onChange: (value: string) => void; required?: boolean }) {
  const id = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-700">{label}</label>
      <input id={id} required={required} value={value} onChange={(e) => onChange(e.target.value)} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-200" />
    </div>
  );
}

export function TextArea({ label, value, onChange, rows = 8 }: { label: string; value: string; onChange: (value: string) => void; rows?: number }) {
  const id = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div className="md:col-span-2">
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-700">{label}</label>
      <textarea id={id} rows={rows} value={value} onChange={(e) => onChange(e.target.value)} className="w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm leading-6 focus:outline-none focus:ring-2 focus:ring-slate-200" />
    </div>
  );
}

export function Select({ label, value, options, onChange, required = false }: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
  required?: boolean;
}) {
  const id = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-700">{label}</label>
      <select id={id} required={required} value={value} onChange={(e) => onChange(e.target.value)} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-200 bg-white">
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

export function NumberField({ label, value, onChange, min, placeholder }: {
  label: string;
  value: number | null;
  onChange: (value: number | null) => void;
  min?: number;
  placeholder?: string;
}) {
  const id = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-700">{label}</label>
      <input
        id={id}
        type="number"
        min={min}
        placeholder={placeholder}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-200"
      />
    </div>
  );
}

export function Checkbox({ label, checked, onChange }: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  const id = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div className="flex items-center gap-2">
      <input id={id} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-200" />
      <label htmlFor={id} className="text-sm font-medium text-slate-700">{label}</label>
    </div>
  );
}

export function StringListField({ label, value, onChange, addLabel = "Add item", placeholder = "Enter value" }: {
  label: string;
  value: string[];
  onChange: (value: string[]) => void;
  addLabel?: string;
  placeholder?: string;
}) {
  return (
    <div className="md:col-span-2">
      <label className="mb-1 block text-sm font-medium text-slate-700">{label}</label>
      <div className="space-y-2">
        {value.map((item, i) => (
          <div key={i} className="flex items-center gap-2">
            <input
              value={item}
              onChange={(e) => { const next = [...value]; next[i] = e.target.value; onChange(next); }}
              placeholder={placeholder}
              className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-200"
            />
            <button type="button" onClick={() => onChange(value.filter((_, j) => j !== i))} className="text-sm text-red-500 hover:text-red-700 px-1">Remove</button>
          </div>
        ))}
        <button type="button" onClick={() => onChange([...value, ""])} className="text-xs font-medium text-slate-600 hover:text-slate-900 rounded border border-slate-300 px-2 py-1">
          + {addLabel}
        </button>
      </div>
    </div>
  );
}

export type KVPair = { key: string; value: string };

export function KeyValueField({ label, value, onChange, addLabel = "Add entry", keyPlaceholder = "Key", valuePlaceholder = "Value" }: {
  label: string;
  value: KVPair[];
  onChange: (value: KVPair[]) => void;
  addLabel?: string;
  keyPlaceholder?: string;
  valuePlaceholder?: string;
}) {
  return (
    <div className="md:col-span-2">
      <label className="mb-1 block text-sm font-medium text-slate-700">{label}</label>
      <div className="space-y-2">
        {value.map((pair, i) => (
          <div key={i} className="flex items-center gap-2">
            <input
              value={pair.key}
              onChange={(e) => { const next = [...value]; next[i] = { ...next[i], key: e.target.value }; onChange(next); }}
              placeholder={keyPlaceholder}
              className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-200"
            />
            <input
              value={pair.value}
              onChange={(e) => { const next = [...value]; next[i] = { ...next[i], value: e.target.value }; onChange(next); }}
              placeholder={valuePlaceholder}
              className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-200"
            />
            <button type="button" onClick={() => onChange(value.filter((_, j) => j !== i))} className="text-sm text-red-500 hover:text-red-700 px-1">Remove</button>
          </div>
        ))}
        <button type="button" onClick={() => onChange([...value, { key: "", value: "" }])} className="text-xs font-medium text-slate-600 hover:text-slate-900 rounded border border-slate-300 px-2 py-1">
          + {addLabel}
        </button>
      </div>
    </div>
  );
}

export function kvToRecord(pairs: KVPair[]): Record<string, string> {
  return Object.fromEntries(pairs.filter((p) => p.key !== "").map((p) => [p.key, p.value]));
}

export function recordToKv(record: Record<string, string> | undefined): KVPair[] {
  if (!record) return [];
  return Object.entries(record).map(([key, value]) => ({ key, value }));
}
