import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

interface Marketplace {
  slug: string;
  displayName: string;
  ownerName: string;
  ownerEmail: string;
  skillCount: number;
}

interface Skill {
  slug: string;
  displayName: string;
  description: string;
  version: string;
}

type Tab = "skills" | "settings";

export default function MarketplaceDetail() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const [marketplace, setMarketplace] = useState<Marketplace | null>(null);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [tab, setTab] = useState<Tab>("skills");
  const [loading, setLoading] = useState(true);

  // Settings form state
  const [settingsForm, setSettingsForm] = useState({ displayName: "", ownerName: "", ownerEmail: "" });
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsMsg, setSettingsMsg] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  const load = async () => {
    setLoading(true);
    const [mktRes, skillsRes] = await Promise.all([
      fetch(`/api/marketplaces/${slug}`),
      fetch(`/api/marketplaces/${slug}/skills`),
    ]);
    if (!mktRes.ok) { navigate("/"); return; }
    const mkt = await mktRes.json();
    const skls = await skillsRes.json();
    setMarketplace(mkt);
    setSkills(skls);
    setSettingsForm({ displayName: mkt.displayName, ownerName: mkt.ownerName, ownerEmail: mkt.ownerEmail });
    setLoading(false);
  };

  useEffect(() => { load(); }, [slug]);

  const handleDeleteSkill = async (skillSlug: string) => {
    if (!confirm(`Delete skill "${skillSlug}"?`)) return;
    await fetch(`/api/marketplaces/${slug}/skills/${skillSlug}`, { method: "DELETE" });
    load();
  };

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setSettingsSaving(true);
    setSettingsMsg("");
    const r = await fetch(`/api/marketplaces/${slug}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settingsForm),
    });
    setSettingsSaving(false);
    if (r.ok) {
      setSettingsMsg("Saved.");
      load();
    } else {
      setSettingsMsg("Save failed.");
    }
  };

  const handleDeleteMarketplace = async () => {
    await fetch(`/api/marketplaces/${slug}`, { method: "DELETE" });
    navigate("/");
  };

  if (loading) return <div className="p-8 text-gray-500">Loading…</div>;
  if (!marketplace) return null;

  // The snippet users copy into Claude Code
  const connectSnippet = `/plugin marketplace add ${window.location.origin}/m/${slug}`;
  const codexRepoUrl = `${window.location.origin}/m/${slug}/git/repo.git`;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center gap-3">
          <Link to="/" className="text-gray-500 hover:text-gray-900 text-sm">← Marketplaces</Link>
          <span className="text-gray-300">/</span>
          <h1 className="text-lg font-semibold text-gray-900">{marketplace.displayName}</h1>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-6">
        {/* Connect snippet */}
        <div className="bg-indigo-50 border border-indigo-200 rounded-lg px-4 py-3 mb-6 space-y-3">
          <div>
            <p className="text-xs font-medium text-indigo-700 mb-1">Add to Claude Code</p>
            <div className="flex items-center gap-2">
              <code className="text-sm text-indigo-900 font-mono flex-1 break-all">{connectSnippet}</code>
              <button
                onClick={() => navigator.clipboard.writeText(connectSnippet)}
                className="text-xs text-indigo-600 hover:text-indigo-900 whitespace-nowrap"
              >
                Copy
              </button>
            </div>
          </div>
          <div className="border-t border-indigo-200 pt-3">
            <p className="text-xs font-medium text-indigo-700 mb-1">Codex-compatible git repo</p>
            <div className="flex items-center gap-2">
              <code className="text-sm text-indigo-900 font-mono flex-1 break-all">{codexRepoUrl}</code>
              <button
                onClick={() => navigator.clipboard.writeText(codexRepoUrl)}
                className="text-xs text-indigo-600 hover:text-indigo-900 whitespace-nowrap"
              >
                Copy
              </button>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200 mb-6 flex gap-6">
          {(["skills", "settings"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`pb-2 text-sm font-medium capitalize ${
                tab === t
                  ? "border-b-2 border-indigo-600 text-indigo-600"
                  : "text-gray-500 hover:text-gray-900"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {tab === "skills" && (
          <div>
            <div className="flex justify-end mb-4">
              <Link
                to={`/m/${slug}/skills/new`}
                className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700"
              >
                Add skill
              </Link>
            </div>
            {skills.length === 0 ? (
              <p className="text-gray-500 text-center py-12">
                No skills yet.{" "}
                <Link to={`/m/${slug}/skills/new`} className="text-indigo-600 hover:underline">
                  Add one
                </Link>
                .
              </p>
            ) : (
              <ul className="space-y-3">
                {skills.map((s) => (
                  <li key={s.slug} className="bg-white rounded-lg border border-gray-200 px-5 py-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-900">{s.displayName}</p>
                        <p className="text-sm text-gray-500 mt-0.5 truncate">{s.description}</p>
                        <p className="text-xs text-gray-400 mt-1 font-mono">v{s.version} · {s.slug}</p>
                      </div>
                      <div className="flex gap-3 shrink-0">
                        <Link
                          to={`/m/${slug}/skills/${s.slug}/edit`}
                          className="text-sm text-indigo-600 hover:underline"
                        >
                          Edit
                        </Link>
                        <button
                          onClick={() => handleDeleteSkill(s.slug)}
                          className="text-sm text-red-500 hover:text-red-700"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {tab === "settings" && (
          <div className="max-w-lg space-y-8">
            <form onSubmit={handleSaveSettings} className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
              <h2 className="text-sm font-semibold text-gray-700">Marketplace details</h2>
              <SettingsField
                label="Name"
                value={settingsForm.displayName}
                onChange={(v) => setSettingsForm((f) => ({ ...f, displayName: v }))}
              />
              <SettingsField
                label="Owner name"
                value={settingsForm.ownerName}
                onChange={(v) => setSettingsForm((f) => ({ ...f, ownerName: v }))}
              />
              <SettingsField
                label="Owner email"
                type="email"
                value={settingsForm.ownerEmail}
                onChange={(v) => setSettingsForm((f) => ({ ...f, ownerEmail: v }))}
              />
              <div className="flex items-center gap-3">
                <button
                  type="submit"
                  disabled={settingsSaving}
                  className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 disabled:opacity-50"
                >
                  {settingsSaving ? "Saving…" : "Save"}
                </button>
                {settingsMsg && <span className="text-sm text-gray-500">{settingsMsg}</span>}
              </div>
            </form>

            <div className="bg-white rounded-lg border border-red-200 p-6">
              <h2 className="text-sm font-semibold text-red-700 mb-2">Danger zone</h2>
              <p className="text-sm text-gray-600 mb-4">
                Deleting this marketplace removes all skills and the git repository permanently.
              </p>
              {deleteConfirm ? (
                <div className="flex gap-3">
                  <button
                    onClick={handleDeleteMarketplace}
                    className="px-4 py-2 bg-red-600 text-white text-sm rounded-md hover:bg-red-700"
                  >
                    Yes, delete permanently
                  </button>
                  <button
                    onClick={() => setDeleteConfirm(false)}
                    className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setDeleteConfirm(true)}
                  className="px-4 py-2 border border-red-400 text-red-600 text-sm rounded-md hover:bg-red-50"
                >
                  Delete marketplace
                </button>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function SettingsField({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
}) {
  const inputId = `settings-${label.toLowerCase().replace(/\s+/g, "-")}`;

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
        className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
      />
    </div>
  );
}
