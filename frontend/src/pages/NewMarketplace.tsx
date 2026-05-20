import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMe } from "../lib/auth";

export default function NewMarketplace() {
  const navigate = useNavigate();
  const { me } = useMe();
  const [form, setForm] = useState({ displayName: "", ownerName: "", ownerEmail: "" });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (me?.displayName && !form.ownerName) setForm((f) => ({ ...f, ownerName: me.displayName ?? "" }));
    if (me?.email && !form.ownerEmail) setForm((f) => ({ ...f, ownerEmail: me.email ?? "" }));
  }, [me]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const r = await fetch("/api/marketplaces", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (r.status === 409) {
        setError("A marketplace with that name already exists.");
        return;
      }
      if (!r.ok) {
        let detail = "";
        try {
          const payload = await r.json();
          detail = typeof payload.detail === "string" ? ` ${payload.detail}` : "";
        } catch {
          detail = "";
        }
        setError(`Failed to create marketplace.${detail}`);
        return;
      }
      const data = await r.json();
      navigate(`/manage/marketplaces/${data.slug}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <main className="mx-auto max-w-lg px-4 py-6">
        <nav className="mb-4 flex items-center gap-2 text-sm">
          <Link to="/manage" className="text-slate-500 hover:text-slate-900">Marketplaces</Link>
          <span className="text-slate-300">/</span>
          <span className="font-medium text-slate-950">New marketplace</span>
        </nav>
        <form onSubmit={handleSubmit} className="rounded-lg border border-slate-200 bg-white p-6 space-y-5">
          <Field
            label="Marketplace name"
            value={form.displayName}
            onChange={(v) => setForm((f) => ({ ...f, displayName: v }))}
            placeholder="Finance Team Skills"
            required
          />
          <Field
            label="Owner name"
            value={form.ownerName}
            onChange={(v) => setForm((f) => ({ ...f, ownerName: v }))}
            placeholder="Alice Smith"
            required
          />
          <Field
            label="Owner email"
            type="email"
            value={form.ownerEmail}
            onChange={(v) => setForm((f) => ({ ...f, ownerEmail: v }))}
            placeholder="alice@company.com"
            required
          />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={saving}
              className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {saving ? "Creating…" : "Create marketplace"}
            </button>
            <button
              type="button"
              onClick={() => navigate("/manage")}
              className="px-4 py-2 text-sm text-slate-600 hover:text-slate-900"
            >
              Cancel
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  required,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  required?: boolean;
  type?: string;
}) {
  const inputId = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div>
      <label htmlFor={inputId} className="mb-1 block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        id={inputId}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-200"
      />
    </div>
  );
}
