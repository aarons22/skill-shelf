import { FormEvent, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useMe } from "../lib/auth";

interface Provider {
  slug: string;
  displayName: string;
  providerType: string;
  kind: "credentials" | "redirect" | "trusted_header";
  loginUrl: string;
}

export default function Login() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const navigate = useNavigate();
  const location = useLocation();
  const { refresh } = useMe();
  const from = (location.state as { from?: string } | null)?.from || "/manage";

  useEffect(() => {
    fetch("/api/auth/providers").then((r) => r.json()).then(setProviders);
  }, []);

  const submitLocal = async (event: FormEvent) => {
    event.preventDefault();
    setMessage("");
    const res = await fetch("/auth/login/local", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      setMessage("Sign-in failed.");
      return;
    }
    const data = await res.json();
    await refresh();
    navigate(data.mustChangePassword ? "/change-password" : from, { replace: true });
  };

  return (
    <main className="mx-auto max-w-md px-4 py-12">
      <h1 className="text-xl font-semibold text-slate-950">Sign in</h1>
      <div className="mt-6 space-y-4">
        {providers.length === 0 && <p className="text-sm text-slate-600">No auth providers configured. Contact your administrator.</p>}
        {providers.map((provider) => (
          <section key={provider.slug} className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">{provider.displayName}</h2>
            {provider.kind === "credentials" && (
              <form onSubmit={submitLocal} className="mt-4 space-y-3">
                <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
                <input value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" type="password" className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
                <button className="w-full rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">Sign in</button>
              </form>
            )}
            {provider.kind === "redirect" && (
              <a href={`${provider.loginUrl}?return_to=${encodeURIComponent(from)}`} className="mt-4 inline-flex rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">Sign in with {provider.displayName}</a>
            )}
            {provider.kind === "trusted_header" && (
              <p className="mt-3 text-sm text-slate-600">Your access proxy signs you in automatically when it sends the expected identity headers.</p>
            )}
          </section>
        ))}
      </div>
      {message && <p className="mt-4 text-sm text-red-600">{message}</p>}
    </main>
  );
}
