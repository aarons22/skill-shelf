import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

interface Marketplace {
  slug: string;
  displayName: string;
  ownerName: string;
  pluginCount: number;
  skillCount: number;
}

export default function BrowseMarketplaces() {
  const [marketplaces, setMarketplaces] = useState<Marketplace[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/marketplaces")
      .then((r) => r.json())
      .then(setMarketplaces)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
          <div>
            <h1 className="text-lg font-semibold text-slate-950">SkillShelf</h1>
            <p className="text-xs text-slate-500">Browse and install plugin marketplaces</p>
          </div>
          <Link to="/manage" className="text-sm text-slate-500 hover:text-slate-900">
            Manage →
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8">
        {loading ? (
          <p className="text-sm text-slate-500">Loading...</p>
        ) : marketplaces.length === 0 ? (
          <div className="py-16 text-center">
            <p className="mb-2 text-slate-700">No marketplaces yet.</p>
            <p className="mb-6 text-sm text-slate-500">
              Create your first marketplace to start sharing plugins with your team.
            </p>
            <Link
              to="/manage/marketplaces/new"
              className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
            >
              Create a marketplace
            </Link>
          </div>
        ) : (
          <>
            <p className="mb-6 text-sm text-slate-500">
              Click a marketplace to see its plugins and get the install command for Claude Code.
            </p>
            <ul className="space-y-3">
              {marketplaces.map((m) => (
                <li key={m.slug}>
                  <Link
                    to={`/marketplaces/${m.slug}`}
                    className="block rounded-lg border border-slate-200 bg-white px-5 py-4 transition-colors hover:border-slate-400"
                  >
                    <div className="flex items-center justify-between gap-4">
                      <div className="min-w-0">
                        <p className="font-medium text-slate-950">{m.displayName}</p>
                        <p className="mt-0.5 text-sm text-slate-500">
                          {m.pluginCount} plugin{m.pluginCount !== 1 ? "s" : ""}
                          {m.skillCount > 0 && ` · ${m.skillCount} skill${m.skillCount !== 1 ? "s" : ""}`}
                          {" · "}maintained by {m.ownerName}
                        </p>
                      </div>
                      <span className="shrink-0 font-mono text-xs text-slate-400">{m.slug}</span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </>
        )}
      </main>
    </div>
  );
}
