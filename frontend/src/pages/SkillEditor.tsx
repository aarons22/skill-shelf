import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

interface Marketplace {
  slug: string;
  displayName: string;
}

interface Skill {
  slug: string;
  displayName: string;
  description: string;
  version: string;
  content?: string;
}

interface SkillForm {
  displayName: string;
  description: string;
  content: string;
}

const emptyForm: SkillForm = {
  displayName: "",
  description: "",
  content: "",
};

export default function SkillEditor() {
  const { slug, skillSlug } = useParams<{ slug: string; skillSlug?: string }>();
  const navigate = useNavigate();
  const isEditing = Boolean(skillSlug);

  const [marketplace, setMarketplace] = useState<Marketplace | null>(null);
  const [form, setForm] = useState<SkillForm>(emptyForm);
  const [skillVersion, setSkillVersion] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const detailPath = useMemo(() => `/m/${slug ?? ""}`, [slug]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (!slug) return;
      setLoading(true);
      setError("");

      try {
        const marketplaceRes = await fetch(`/api/marketplaces/${slug}`);
        if (!marketplaceRes.ok) {
          navigate("/");
          return;
        }

        const marketplaceData = await marketplaceRes.json() as Marketplace;
        if (cancelled) return;
        setMarketplace(marketplaceData);

        if (isEditing && skillSlug) {
          const skillRes = await fetch(`/api/marketplaces/${slug}/skills/${skillSlug}`);
          if (skillRes.status === 404) {
            navigate(detailPath);
            return;
          }
          if (!skillRes.ok) {
            throw new Error("Failed to load skill.");
          }

          const skill = await skillRes.json() as Skill;
          if (cancelled) return;
          setForm({
            displayName: skill.displayName,
            description: skill.description,
            content: skill.content ?? "",
          });
          setSkillVersion(skill.version);
        } else if (!cancelled) {
          setForm(emptyForm);
          setSkillVersion("");
        }
      } catch {
        if (!cancelled) setError("Could not load this skill.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [detailPath, isEditing, navigate, skillSlug, slug]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!slug) return;

    setSaving(true);
    setError("");

    const url = isEditing
      ? `/api/marketplaces/${slug}/skills/${skillSlug}`
      : `/api/marketplaces/${slug}/skills`;
    const method = isEditing ? "PUT" : "POST";

    try {
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });

      if (res.status === 409) {
        setError("A skill with that name already exists in this marketplace.");
        return;
      }
      if (!res.ok) {
        setError(isEditing ? "Failed to save this skill." : "Failed to create this skill.");
        return;
      }

      navigate(detailPath);
    } catch {
      setError("The server could not be reached.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="min-h-screen bg-slate-50 p-8 text-sm text-slate-500">Loading...</div>;
  }

  if (!marketplace) return null;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-4">
          <Link to="/" className="text-sm text-slate-500 hover:text-slate-900">
            Marketplaces
          </Link>
          <span className="text-slate-300">/</span>
          <Link to={detailPath} className="text-sm text-slate-500 hover:text-slate-900">
            {marketplace.displayName}
          </Link>
          <span className="text-slate-300">/</span>
          <h1 className="text-lg font-semibold text-slate-950">
            {isEditing ? "Edit skill" : "Add skill"}
          </h1>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8">
        <form onSubmit={handleSubmit} className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
          <section className="space-y-5 rounded-lg border border-slate-200 bg-white p-6">
            <Field
              label="Skill name"
              value={form.displayName}
              onChange={(value) => setForm((current) => ({ ...current, displayName: value }))}
              placeholder="Quarterly Report Process"
              required
            />
            <Field
              label="Description"
              value={form.description}
              onChange={(value) => setForm((current) => ({ ...current, description: value }))}
              placeholder="Generate the finance team's quarterly reporting workflow."
              required
            />
            <div>
              <label htmlFor="content" className="mb-1 block text-sm font-medium text-slate-700">
                Instructions
              </label>
              <textarea
                id="content"
                value={form.content}
                onChange={(e) => setForm((current) => ({ ...current, content: e.target.value }))}
                required
                rows={18}
                className="min-h-[420px] w-full resize-y rounded-md border border-slate-300 px-3 py-2 font-mono text-sm leading-6 text-slate-900 shadow-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
                placeholder="Write the skill instructions here."
              />
            </div>
          </section>

          <aside className="h-fit rounded-lg border border-slate-200 bg-white p-5">
            <div className="space-y-3">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Marketplace</p>
                <p className="mt-1 text-sm font-medium text-slate-950">{marketplace.displayName}</p>
                <p className="mt-0.5 break-all font-mono text-xs text-slate-500">{marketplace.slug}</p>
              </div>
              {isEditing && (
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Current version</p>
                  <p className="mt-1 font-mono text-sm text-slate-700">v{skillVersion}</p>
                </div>
              )}
              {error && (
                <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {error}
                </p>
              )}
              <div className="flex flex-col gap-2 pt-2">
                <button
                  type="submit"
                  disabled={saving}
                  className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {saving ? "Saving..." : isEditing ? "Save changes" : "Create skill"}
                </button>
                <button
                  type="button"
                  onClick={() => navigate(detailPath)}
                  className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          </aside>
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
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
}) {
  const inputId = label.toLowerCase().replace(/\s+/g, "-");

  return (
    <div>
      <label htmlFor={inputId} className="mb-1 block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        id={inputId}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
      />
    </div>
  );
}
