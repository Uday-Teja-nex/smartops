"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { Lock, ShieldCheck } from "lucide-react";
import { useAuth } from "@/app/auth";

const DEMO_ACCOUNTS = [
  { email: "admin@smartops.local", role: "Admin" },
  { email: "supervisor@smartops.local", role: "Supervisor" },
  { email: "operator@smartops.local", role: "Operator" },
  { email: "viewer@smartops.local", role: "Viewer" },
  { email: "security@smartops.local", role: "Security" },
  { email: "ehs@smartops.local", role: "EHS" },
];

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState("operator@smartops.local");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email.trim().toLowerCase(), password);
      router.replace("/");
    } catch (err) {
      setError(
        err instanceof Error && err.message.includes("401")
          ? "Invalid email or password."
          : "Could not reach the SmartOps API. Is the Docker stack running?"
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/90 p-8 shadow-2xl backdrop-blur">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-300">
              <ShieldCheck className="h-5 w-5" />
            </span>
            <div>
              <h1 className="text-lg font-semibold text-slate-100">SmartOps</h1>
              <p className="text-xs text-slate-400">Smart-building CCTV operations console</p>
            </div>
          </div>

          <form onSubmit={submit} className="mt-8 space-y-4">
            <label className="block text-sm">
              <span className="text-slate-400">Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
                required
                className="mt-1 w-full rounded-lg border border-[color:var(--border)] bg-[color:var(--surface-2)] px-3 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-400"
              />
            </label>
            <label className="block text-sm">
              <span className="text-slate-400">Password</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                className="mt-1 w-full rounded-lg border border-[color:var(--border)] bg-[color:var(--surface-2)] px-3 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-400"
              />
            </label>

            {error && (
              <p className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-lg bg-emerald-500 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:opacity-50"
            >
              {busy ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <div className="mt-8 rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-2)]/60 p-4">
            <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              <Lock className="h-3.5 w-3.5" /> Local demo accounts
            </p>
            <p className="mt-1 text-[11px] text-slate-500">
              Seeded for local development only. Password for all accounts:{" "}
              <code className="rounded bg-slate-800 px-1 py-0.5 text-emerald-300">smartops-demo</code>
            </p>
            <div className="mt-3 grid grid-cols-2 gap-1.5">
              {DEMO_ACCOUNTS.map((account) => (
                <button
                  key={account.email}
                  type="button"
                  onClick={() => setEmail(account.email)}
                  className="rounded-lg border border-transparent bg-slate-800/60 px-2 py-1.5 text-left text-[11px] text-slate-300 transition hover:border-emerald-500/40 hover:text-emerald-200"
                >
                  <span className="block font-semibold">{account.role}</span>
                  <span className="block truncate text-slate-500">{account.email}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
