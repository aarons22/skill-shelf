import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMe } from "../lib/auth";

export default function SetupWizard() {
  const [step, setStep] = useState(1);
  const [displayName, setDisplayName] = useState("Default Organization");
  const [ownerName, setOwnerName] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [accessMode, setAccessMode] = useState<"public" | "authenticated" | "restricted">("public");
  const [email, setEmail] = useState("");
  const [adminName, setAdminName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState("");
  const navigate = useNavigate();
  const { refresh } = useMe();

  const finish = async (event: FormEvent) => {
    event.preventDefault();
    if (password !== confirm) {
      setMessage("Passwords do not match.");
      return;
    }
    const res = await fetch("/api/organization/setup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        displayName,
        ownerName,
        ownerEmail,
        accessMode,
        marketplaceCreation: "authenticated",
        provider: {
          provider: "local",
          admin: { email, displayName: adminName || email, password },
        },
      }),
    });
    if (!res.ok) {
      setMessage(res.status === 409 ? "Setup has already been completed by another user. Sign in instead." : "Setup could not be completed.");
      return;
    }
    await refresh();
    navigate("/manage", { replace: true });
  };

  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-semibold text-slate-950">Set up SkillShelf</h1>
      <div className="mt-6 rounded-lg border border-slate-200 bg-white p-6">
        <div className="mb-6 flex gap-2">
          {[1, 2, 3, 4].map((item) => <span key={item} className={`h-2 flex-1 rounded-full ${item <= step ? "bg-slate-950" : "bg-slate-200"}`} />)}
        </div>
        {step === 1 && (
          <div className="space-y-4">
            <Field label="Organization name" value={displayName} onChange={setDisplayName} />
            <Field label="Owner name" value={ownerName} onChange={setOwnerName} />
            <Field label="Owner email" value={ownerEmail} onChange={setOwnerEmail} />
            <button onClick={() => setStep(2)} className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white">Continue</button>
          </div>
        )}
        {step === 2 && (
          <div className="space-y-4">
            {(["public", "authenticated", "restricted"] as const).map((mode) => (
              <label key={mode} className="flex items-start gap-3 rounded-md border border-slate-200 p-4">
                <input type="radio" checked={accessMode === mode} onChange={() => setAccessMode(mode)} className="mt-1" />
                <span><span className="block font-medium capitalize text-slate-900">{mode}</span><span className="text-sm text-slate-600">{mode === "public" ? "Anonymous reads allowed; writes require login." : mode === "authenticated" ? "All reads require login." : "Reads require explicit grants."}</span></span>
              </label>
            ))}
            <button onClick={() => setStep(3)} className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white">Continue</button>
          </div>
        )}
        {step === 3 && (
          <div className="space-y-4">
            <p className="text-sm font-medium text-slate-900">Local Accounts</p>
            <Field label="Admin email" value={email} onChange={setEmail} />
            <Field label="Admin display name" value={adminName} onChange={setAdminName} />
            <Field label="Password" value={password} onChange={setPassword} type="password" />
            <Field label="Confirm password" value={confirm} onChange={setConfirm} type="password" />
            <button onClick={() => setStep(4)} className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white">Review</button>
          </div>
        )}
        {step === 4 && (
          <form onSubmit={finish} className="space-y-4">
            <div className="rounded-md bg-slate-50 p-4 text-sm text-slate-700">
              <p><strong>{displayName}</strong></p>
              <p>Access mode: {accessMode}</p>
              <p>Admin: {adminName || email} ({email})</p>
            </div>
            <button className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white">Finish setup</button>
          </form>
        )}
        {message && <p className="mt-4 text-sm text-red-600">{message}</p>}
      </div>
    </main>
  );
}

function Field({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700">{label}</span>
      <input value={value} onChange={(e) => onChange(e.target.value)} type={type} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
    </label>
  );
}
