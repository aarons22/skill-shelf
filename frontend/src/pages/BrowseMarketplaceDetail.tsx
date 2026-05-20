import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import CopyLine from "../components/CopyLine";

interface Marketplace {
  slug: string;
  displayName: string;
  ownerName: string;
}

interface Plugin {
  slug: string;
  displayName: string;
  description: string;
  version: string;
  skillCount: number;
  hookCount: number;
  agentCount: number;
  mcpServerCount: number;
  commandCount: number;
  monitorCount: number;
  hasSettings: boolean;
}

function componentSummary(p: Plugin): string {
  const parts: string[] = [];
  if (p.skillCount) parts.push(`${p.skillCount} skill${p.skillCount !== 1 ? "s" : ""}`);
  if (p.hookCount) parts.push(`${p.hookCount} hook${p.hookCount !== 1 ? "s" : ""}`);
  if (p.agentCount) parts.push(`${p.agentCount} agent${p.agentCount !== 1 ? "s" : ""}`);
  if (p.mcpServerCount) parts.push(`${p.mcpServerCount} MCP`);
  if (p.commandCount) parts.push(`${p.commandCount} command${p.commandCount !== 1 ? "s" : ""}`);
  if (p.monitorCount) parts.push(`${p.monitorCount} monitor${p.monitorCount !== 1 ? "s" : ""}`);
  if (p.hasSettings) parts.push("settings");
  return parts.length ? parts.join(" · ") : "No components";
}

export default function BrowseMarketplaceDetail() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const [marketplace, setMarketplace] = useState<Marketplace | null>(null);
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!slug) return;
    Promise.all([
      fetch(`/api/marketplaces/${slug}`),
      fetch(`/api/marketplaces/${slug}/plugins`),
    ]).then(async ([mktRes, pluginsRes]) => {
      if (!mktRes.ok) { navigate("/"); return; }
      const [mkt, plugs] = await Promise.all([mktRes.json(), pluginsRes.ok ? pluginsRes.json() : []]);
      setMarketplace(mkt);
      setPlugins(plugs);
      setLoading(false);
    });
  }, [slug]);

  if (loading) return <div className="p-8 text-sm text-slate-500">Loading...</div>;
  if (!marketplace) return null;

  const connectSnippet = `/plugin marketplace add ${window.location.origin}/m/${slug}`;
  const gitRepoUrl = `${window.location.origin}/m/${slug}/git/repo.git`;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-4">
          <Link to="/" className="text-sm text-slate-500 hover:text-slate-900">Marketplaces</Link>
          <span className="text-slate-300">/</span>
          <h1 className="text-lg font-semibold text-slate-950">{marketplace.displayName}</h1>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6">
        <div className="mb-6 space-y-3 rounded-lg border border-slate-200 bg-white px-4 py-4">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-sm text-slate-700">
              Maintained by <span className="font-medium">{marketplace.ownerName}</span>
            </p>
            <Link to="/manage" className="text-xs text-slate-400 hover:text-slate-700">
              Manage →
            </Link>
          </div>
          <CopyLine label="Add to Claude Code" value={connectSnippet} />
          <CopyLine label="Codex-compatible git repo" value={gitRepoUrl} />
        </div>

        {plugins.length === 0 ? (
          <p className="py-12 text-center text-sm text-slate-500">
            No plugins in this marketplace yet.
          </p>
        ) : (
          <>
            <p className="mb-4 text-sm text-slate-500">
              After connecting the marketplace, install individual plugins with{" "}
              <code className="font-mono text-xs">/plugin install &lt;name&gt;@{slug}</code>.
            </p>
            <ul className="space-y-3">
              {plugins.map((plugin) => (
                <li key={plugin.slug} className="rounded-lg border border-slate-200 bg-white px-5 py-4">
                  <div className="mb-3">
                    <div className="flex items-baseline justify-between gap-3">
                      <p className="font-medium text-slate-950">{plugin.displayName}</p>
                      <span className="shrink-0 font-mono text-xs text-slate-400">v{plugin.version}</span>
                    </div>
                    {plugin.description && (
                      <p className="mt-0.5 text-sm text-slate-500">{plugin.description}</p>
                    )}
                    <p className="mt-1 text-xs text-slate-400">{componentSummary(plugin)}</p>
                  </div>
                  <CopyLine
                    label="Install command"
                    value={`/plugin install ${plugin.slug}@${slug}`}
                  />
                </li>
              ))}
            </ul>
          </>
        )}
      </main>
    </div>
  );
}
