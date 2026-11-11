"use client";

import { FormEvent, useState } from "react";
import { KeyRound } from "lucide-react";
import { useAuth } from "@/app/auth";
import { SectionHeader } from "@/components/SectionHeader";
import { Button } from "@/components/ui/Button";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { changeOwnPassword } from "@/lib/api";

const inputClass =
  "mt-1 w-full rounded-lg border border-[color:var(--glass-border)] bg-white/5 px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-[color:var(--accent)]";

export default function AccountPage() {
  const { user } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (next !== confirm) {
      setMessage({ ok: false, text: "The new passwords do not match." });
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      await changeOwnPassword(current, next);
      setCurrent("");
      setNext("");
      setConfirm("");
      setMessage({ ok: true, text: "Password changed. Your other signed-in browsers have been signed out." });
    } catch (err) {
      const text = err instanceof Error ? err.message : "Could not change the password";
      setMessage({ ok: false, text: text.includes("400") ? "Your current password is incorrect." : text });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <SectionHeader title="Account" subtitle={user ? `${user.name} · ${user.email} · ${user.role}` : "Your account"} />
      <GlassPanel className="max-w-lg">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-300">
          <KeyRound className="h-4 w-4 text-[color:var(--accent)]" /> Change password
        </h3>
        <form onSubmit={(event) => void submit(event)} className="mt-4 space-y-3">
          <label className="block text-xs text-slate-400">Current password
            <input required type="password" autoComplete="current-password" className={inputClass}
              value={current} onChange={(e) => setCurrent(e.target.value)} />
          </label>
          <label className="block text-xs text-slate-400">New password (at least 12 characters)
            <input required minLength={12} type="password" autoComplete="new-password" className={inputClass}
              value={next} onChange={(e) => setNext(e.target.value)} />
          </label>
          <label className="block text-xs text-slate-400">Repeat new password
            <input required minLength={12} type="password" autoComplete="new-password" className={inputClass}
              value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </label>
          {message && (
            <p role={message.ok ? "status" : "alert"}
              className={`rounded-lg px-3 py-2 text-xs ${message.ok ? "bg-emerald-500/10 text-emerald-200" : "bg-rose-500/10 text-rose-200"}`}>
              {message.text}
            </p>
          )}
          <Button type="submit" variant="primary" size="sm" disabled={busy}>{busy ? "Saving…" : "Change password"}</Button>
        </form>
      </GlassPanel>
    </div>
  );
}
