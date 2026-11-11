"use client";

import { FormEvent, useEffect, useState } from "react";
import { KeyRound, UserPlus, Users } from "lucide-react";
import { useAuth } from "@/app/auth";
import { Button } from "@/components/ui/Button";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { fetchUsers, inviteUser, resetUserPassword, updateUser } from "@/lib/api";
import { UserRecord, UserRole } from "@/lib/types";

const ROLES: UserRole[] = ["viewer", "operator", "security", "ehs", "supervisor", "admin"];
const inputClass =
  "w-full rounded-lg border border-[color:var(--glass-border)] bg-white/5 px-2.5 py-1.5 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-[color:var(--accent)]";

/** Shown once after an invite or reset; never stored in the browser. */
const OneTimePassword = ({ email, password, onDone }: { email: string; password: string; onDone: () => void }) => (
  <div role="status" className="mt-3 rounded-xl bg-emerald-500/10 p-3 text-sm text-emerald-100">
    <p>Temporary password for <span className="font-semibold">{email}</span>, shown only now. Hand it over securely; they
      should change it under Account after signing in.</p>
    <code className="mt-2 block break-all rounded bg-black/30 px-2 py-1 font-mono text-emerald-200">{password}</code>
    <Button size="sm" className="mt-2" onClick={onDone}>Done</Button>
  </div>
);

export const UserManagement = () => {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<UserRecord[] | null>(null);
  const [version, setVersion] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [secret, setSecret] = useState<{ email: string; password: string } | null>(null);
  const [form, setForm] = useState({ email: "", name: "", role: "operator" as UserRole });
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchUsers().then((next) => { if (active) { setUsers(next); setError(null); } })
      .catch((err: unknown) => { if (active) setError(err instanceof Error ? err.message : "Could not load users"); });
    return () => { active = false; };
  }, [version]);

  const run = async (key: string, action: () => Promise<void>) => {
    setBusy(key);
    setError(null);
    try {
      await action();
      setVersion((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(null);
    }
  };

  const invite = (event: FormEvent) => {
    event.preventDefault();
    void run("invite", async () => {
      const result = await inviteUser({ email: form.email.trim(), name: form.name.trim(), role: form.role });
      setSecret({ email: result.user.email, password: result.temporaryPassword });
      setForm({ email: "", name: "", role: "operator" });
    });
  };

  return (
    <GlassPanel className="xl:col-span-2">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-300">
        <Users className="h-4 w-4 text-[color:var(--accent)]" /> Users
      </h3>
      <form onSubmit={invite} className="mt-4 grid gap-2 md:grid-cols-[2fr_2fr_1fr_auto]">
        <input required type="email" aria-label="Email" placeholder="name@company.com" className={inputClass}
          value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <input required aria-label="Name" placeholder="Full name" className={inputClass}
          value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <select aria-label="Role" className={inputClass} value={form.role}
          onChange={(e) => setForm({ ...form, role: e.target.value as UserRole })}>
          {ROLES.map((role) => <option key={role} value={role}>{role}</option>)}
        </select>
        <Button type="submit" size="sm" variant="primary" disabled={busy === "invite"} icon={<UserPlus className="h-3.5 w-3.5" />}>
          {busy === "invite" ? "Inviting…" : "Invite"}
        </Button>
      </form>
      {secret && <OneTimePassword email={secret.email} password={secret.password} onDone={() => setSecret(null)} />}
      {error && <p role="alert" className="mt-3 rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-200">{error}</p>}
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-[11px] uppercase tracking-wide text-slate-600">
            <tr><th className="pb-2 pr-4">Name</th><th className="pb-2 pr-4">Email</th><th className="pb-2 pr-4">Role</th>
              <th className="pb-2 pr-4">Status</th><th className="pb-2" /></tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {users === null && !error && <tr><td className="py-3 text-xs text-slate-500" colSpan={5}>Loading users…</td></tr>}
            {users?.map((item) => {
              const self = item.id === me?.id;
              return (
                <tr key={item.id} className={item.active ? "" : "opacity-60"}>
                  <td className="py-2.5 pr-4 font-semibold text-slate-200">{item.name}{self && <span className="ml-2 text-[10px] text-slate-500">(you)</span>}</td>
                  <td className="py-2.5 pr-4 font-mono text-xs text-slate-400">{item.email}</td>
                  <td className="py-2.5 pr-4">
                    <select aria-label={`Role for ${item.email}`} disabled={self || busy === item.id} className={`${inputClass} w-32`}
                      value={item.role} onChange={(e) => void run(item.id, async () => { await updateUser(item.id, { role: e.target.value as UserRole }); })}>
                      {ROLES.map((role) => <option key={role} value={role}>{role}</option>)}
                    </select>
                  </td>
                  <td className="py-2.5 pr-4 text-xs text-slate-400">{item.active ? "Active" : "Deactivated"}</td>
                  <td className="py-2.5 text-right">
                    {!self && (
                      <div className="flex justify-end gap-1.5">
                        <Button size="sm" variant="ghost" disabled={busy === item.id} icon={<KeyRound className="h-3.5 w-3.5" />}
                          onClick={() => void run(item.id, async () => {
                            const result = await resetUserPassword(item.id);
                            setSecret({ email: item.email, password: result.temporaryPassword });
                          })}>Reset password</Button>
                        <Button size="sm" variant={item.active ? "danger" : "outline"} disabled={busy === item.id}
                          onClick={() => void run(item.id, async () => { await updateUser(item.id, { active: !item.active }); })}>
                          {item.active ? "Deactivate" : "Reactivate"}
                        </Button>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-[11px] text-slate-600">
        Deactivating or resetting a password signs that person out everywhere immediately. You cannot deactivate or
        demote your own account.
      </p>
    </GlassPanel>
  );
};
