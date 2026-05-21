import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMe } from "../lib/auth";

export default function ChangePassword() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState("");
  const navigate = useNavigate();
  const { refresh } = useMe();

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const res = await fetch("/auth/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
    if (!res.ok) {
      setMessage("Could not change password.");
      return;
    }
    await refresh();
    navigate("/manage", { replace: true });
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4">
      <div className="mb-8 text-center">
        <p className="text-2xl font-bold tracking-tight text-slate-950">SkillShelf</p>
        <p className="mt-1 text-sm text-slate-500">Set a new password to continue</p>
      </div>
      <main className="w-full max-w-md">
        <form onSubmit={submit} className="rounded-lg border border-slate-200 bg-white p-5">
          <div className="space-y-3">
            <input value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} placeholder="Current password" type="password" className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
            <input value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="New password" type="password" className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
            <button className="w-full rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">Save password</button>
          </div>
        </form>
        {message && <p className="mt-4 text-sm text-red-600">{message}</p>}
      </main>
    </div>
  );
}
