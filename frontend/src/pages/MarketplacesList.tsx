import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

interface Marketplace {
  slug: string;
  displayName: string;
  ownerName: string;
  pluginCount: number;
  createdAt: number;
}

interface WorkspaceSettings {
  accessMode: "public" | "authenticated" | "restricted";
  marketplaceCreation: "authenticated" | "workspace_admin";
}

export default function MarketplacesList() {
  const [marketplaces, setMarketplaces] = useState<Marketplace[]>([]);
  const [settings, setSettings] = useState<WorkspaceSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [settingsMsg, setSettingsMsg] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([
      fetch("/api/marketplaces").then((r) => r.json()),
      fetch("/api/workspace/settings").then((r) => r.json()),
    ])
      .then(([marketplaceData, settingsData]) => {
        setMarketplaces(marketplaceData);
        setSettings(settingsData);
      })
      .finally(() => setLoading(false));
  }, []);

  const updateSettings = async (updates: Partial<WorkspaceSettings>) => {
    if (!settings) return;
    const next = { ...settings, ...updates };
    setSettings(next);
    setSettingsMsg("");
    const r = await fetch("/api/workspace/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ accessMode: next.accessMode, marketplaceCreation: next.marketplaceCreation }),
    });
    setSettingsMsg(r.ok ? "Saved." : "Save failed.");
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-xl font-semibold text-gray-900">SkillShelf</h1>
          <button
            onClick={() => navigate("/admin/new")}
            className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700"
          >
            New marketplace
          </button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        {settings && (
          <section className="mb-6 rounded-lg border border-gray-200 bg-white p-5">
            <div className="grid gap-4 md:grid-cols-2">
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-gray-700">Workspace access</span>
                <select
                  value={settings.accessMode}
                  onChange={(e) => updateSettings({ accessMode: e.target.value as WorkspaceSettings["accessMode"] })}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                >
                  <option value="public">Public</option>
                  <option value="authenticated">Authenticated</option>
                  <option value="restricted">Restricted</option>
                </select>
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-gray-700">Marketplace creation</span>
                <select
                  value={settings.marketplaceCreation}
                  onChange={(e) => updateSettings({ marketplaceCreation: e.target.value as WorkspaceSettings["marketplaceCreation"] })}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                >
                  <option value="authenticated">Authenticated users</option>
                  <option value="workspace_admin">Workspace admins</option>
                </select>
              </label>
            </div>
            {settingsMsg && <p className="mt-3 text-sm text-gray-500">{settingsMsg}</p>}
          </section>
        )}
        {loading ? (
          <p className="text-gray-500">Loading…</p>
        ) : marketplaces.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-gray-500 mb-4">No marketplaces yet.</p>
            <button
              onClick={() => navigate("/admin/new")}
              className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
            >
              Create your first marketplace
            </button>
          </div>
        ) : (
          <ul className="space-y-3">
            {marketplaces.map((m) => (
              <li key={m.slug}>
                <Link
                  to={`/admin/marketplaces/${m.slug}`}
                  className="block bg-white rounded-lg border border-gray-200 px-5 py-4 hover:border-indigo-400 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-gray-900">{m.displayName}</p>
                      <p className="text-sm text-gray-500 mt-0.5">
                        {m.pluginCount} plugin{m.pluginCount !== 1 ? "s" : ""} · owner: {m.ownerName}
                      </p>
                    </div>
                    <span className="text-gray-400 text-sm font-mono">{m.slug}</span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
