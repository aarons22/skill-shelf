import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useMe } from "../lib/auth";

interface Marketplace {
  slug: string;
  displayName: string;
  ownerName: string;
  pluginCount: number;
  skillCount: number;
}

export default function BrowseMarketplaces() {
  const { me } = useMe();
  const [marketplaces, setMarketplaces] = useState<Marketplace[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/marketplaces")
      .then((r) => r.json())
      .then(setMarketplaces)
      .finally(() => setLoading(false));
  }, []);

  const canManage = (slug: string) =>
    me?.organizationAdmin ||
    me?.marketplaceAdminSlugs.includes(slug) ||
    me?.marketplaceMaintainerSlugs.includes(slug) ||
    me?.marketplaceContributorSlugs.includes(slug);

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-slate-950">Marketplaces</h1>
        {me?.canCreateMarketplace && (
          <Link
            to="/manage/new"
            className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
          >
            New marketplace
          </Link>
        )}
      </div>
      {loading ? (
        <p className="text-sm text-slate-500">Loading...</p>
      ) : marketplaces.length === 0 ? (
        <div className="py-16 text-center">
          {me?.canCreateMarketplace ? (
            <>
              <p className="mb-4 text-slate-500">No marketplaces yet.</p>
              <Link
                to="/manage/new"
                className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
              >
                Create your first marketplace
              </Link>
            </>
          ) : (
            <>
              <p className="mb-2 text-slate-700">No marketplaces yet.</p>
              <p className="text-sm text-slate-500">Check back later or ask your administrator to create one.</p>
            </>
          )}
        </div>
      ) : (
        <ul className="space-y-3">
          {marketplaces.map((m) => (
            <li key={m.slug} className="rounded-lg border border-slate-200 bg-white transition-colors hover:border-slate-400">
              <div className="flex items-center gap-4 px-5 py-4">
                <Link to={`/marketplaces/${m.slug}`} className="min-w-0 flex-1">
                  <p className="font-medium text-slate-950">{m.displayName}</p>
                  <p className="mt-0.5 text-sm text-slate-500">
                    {m.pluginCount} plugin{m.pluginCount !== 1 ? "s" : ""}
                    {m.skillCount > 0 && ` · ${m.skillCount} skill${m.skillCount !== 1 ? "s" : ""}`}
                    {me?.displayName !== m.ownerName && ` · maintained by ${m.ownerName}`}
                  </p>
                </Link>
                <span className="shrink-0 font-mono text-xs text-slate-400">{m.slug}</span>
                {canManage(m.slug) && (
                  <Link
                    to={`/manage/${m.slug}`}
                    className="shrink-0 rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100"
                    onClick={(e) => e.stopPropagation()}
                  >
                    Manage
                  </Link>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
