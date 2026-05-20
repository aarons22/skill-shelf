import { useState } from "react";
import { useNavigate } from "react-router-dom";

export default function NewMarketplace() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ displayName: "", ownerName: "", ownerEmail: "" });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

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
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center gap-3">
          <button onClick={() => navigate("/manage")} className="text-gray-500 hover:text-gray-900 text-sm">
            ← Marketplaces
          </button>
          <span className="text-gray-300">/</span>
          <h1 className="text-lg font-semibold text-gray-900">New marketplace</h1>
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 py-10">
        <form onSubmit={handleSubmit} className="bg-white rounded-lg border border-gray-200 p-6 space-y-5">
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
          {error && <p className="text-red-600 text-sm">{error}</p>}
          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 disabled:opacity-50"
            >
              {saving ? "Creating…" : "Create marketplace"}
            </button>
            <button
              type="button"
              onClick={() => navigate("/manage")}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900"
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
      <label htmlFor={inputId} className="block text-sm font-medium text-gray-700 mb-1">
        {label}
      </label>
      <input
        id={inputId}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
      />
    </div>
  );
}
