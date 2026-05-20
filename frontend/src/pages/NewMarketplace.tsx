import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

export default function NewMarketplace() {
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState("");
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
        body: JSON.stringify({ displayName }),
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
          <div>
            <label htmlFor="display-name" className="mb-1 block text-sm font-medium text-slate-700">
              Marketplace name
            </label>
            <input
              id="display-name"
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Finance Team Skills"
              required
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-200"
            />
          </div>
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
