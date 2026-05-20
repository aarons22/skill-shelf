import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

interface Marketplace {
  slug: string;
  displayName: string;
  ownerName: string;
  pluginCount: number;
  createdAt: number;
}

interface CurrentUser {
  authenticated: boolean;
  organizationAdmin: boolean;
}

export default function MarketplacesList() {
  const [marketplaces, setMarketplaces] = useState<Marketplace[]>([]);
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([
      fetch("/api/marketplaces").then((r) => r.json()),
      fetch("/api/me").then((r) => r.json()),
    ])
      .then(([marketplaceData, meData]) => {
        setMarketplaces(marketplaceData);
        setMe(meData);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-xl font-semibold text-gray-900">Manage marketplaces</h1>
          <div className="flex items-center gap-3">
            {me?.organizationAdmin && (
              <button onClick={() => navigate("/organization")} className="text-sm text-gray-500 hover:text-gray-900">
                Organization settings
              </button>
            )}
            <button
              onClick={() => navigate("/manage/marketplaces/new")}
              className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700"
            >
              New marketplace
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        {loading ? (
          <p className="text-gray-500">Loading…</p>
        ) : marketplaces.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-gray-500 mb-4">No marketplaces yet.</p>
            <button
              onClick={() => navigate("/manage/marketplaces/new")}
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
                  to={`/manage/marketplaces/${m.slug}`}
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
