import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

interface Marketplace {
  slug: string;
  displayName: string;
  ownerName: string;
  pluginCount: number;
  createdAt: number;
}

export default function MarketplacesList() {
  const [marketplaces, setMarketplaces] = useState<Marketplace[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetch("/api/marketplaces")
      .then((r) => r.json())
      .then(setMarketplaces)
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-slate-950">Marketplaces</h1>
        <button
          onClick={() => navigate("/manage/marketplaces/new")}
          className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          New marketplace
        </button>
      </div>
      {loading ? (
        <p className="text-slate-500">Loading…</p>
      ) : marketplaces.length === 0 ? (
        <div className="py-16 text-center">
          <p className="mb-4 text-slate-500">No marketplaces yet.</p>
          <button
            onClick={() => navigate("/manage/marketplaces/new")}
            className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
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
                className="block rounded-lg border border-slate-200 bg-white px-5 py-4 hover:border-slate-400 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-slate-900">{m.displayName}</p>
                    <p className="mt-0.5 text-sm text-slate-500">
                      {m.pluginCount} plugin{m.pluginCount !== 1 ? "s" : ""} · owner: {m.ownerName}
                    </p>
                  </div>
                  <span className="font-mono text-sm text-slate-400">{m.slug}</span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
