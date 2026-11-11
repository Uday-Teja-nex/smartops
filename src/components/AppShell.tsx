"use client";

import Link from "next/link";
import { DegradedBanner } from "@/components/SystemStatus";
import { WorkspaceBadge } from "@/components/WorkspaceBadge";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect } from "react";
import {
  Activity,
  Camera,
  FileBarChart,
  LayoutDashboard,
  LogOut,
  Radio,
  Search,
  Settings,
  ShieldCheck,
} from "lucide-react";
import { useAuth } from "@/app/auth";
import { useSmartOps } from "@/app/providers";
import { TIME_RANGE_LABELS } from "@/lib/analytics";
import { UserRole } from "@/lib/types";
import { classNames } from "@/lib/utils";
import { ErrorState } from "@/components/ui/EmptyState";
import { SkeletonPanel } from "@/components/ui/Skeleton";

type NavItem = {
  name: string;
  href: string;
  icon: typeof LayoutDashboard;
  minRole?: UserRole;
};

const NAV_ITEMS: NavItem[] = [
  { name: "Overview", href: "/", icon: LayoutDashboard },
  { name: "Live Ops", href: "/live-ops", icon: Activity },
  { name: "Camera view", href: "/cameras", icon: Camera },
  { name: "Sources", href: "/sources", icon: Camera },
  { name: "Monitoring", href: "/monitoring", icon: Radio },
  { name: "Reports", href: "/reports", icon: FileBarChart },
  { name: "Settings", href: "/settings", icon: Settings, minRole: "supervisor" },
];

export const AppShell = ({ children }: { children: ReactNode }) => {
  const pathname = usePathname();
  const router = useRouter();
  const { user, initializing, logout, hasRole } = useAuth();
  const {
    backendStatus,
    actionError,
    runtime,
    buildings,
    selectedBuildingId,
    setSelectedBuildingId,
    timeRange,
    setTimeRange,
    searchQuery,
    setSearchQuery,
  } = useSmartOps();

  const isLoginRoute = pathname === "/login";

  useEffect(() => {
    if (!initializing && !user && !isLoginRoute) {
      router.replace("/login");
    }
    if (!initializing && user && isLoginRoute) {
      router.replace("/");
    }
  }, [initializing, user, isLoginRoute, router]);

  if (isLoginRoute) {
    return (
      <div className="min-h-screen bg-[color:var(--bg)] text-[color:var(--text)]">
        {children}
      </div>
    );
  }

  if (initializing || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[color:var(--bg)] text-[color:var(--text)]">
        <div className="flex items-center gap-3 text-sm text-slate-400">
          <span className="pulse-dot h-2 w-2 rounded-full bg-[color:var(--accent)]" />
          {initializing ? "Checking session…" : "Redirecting to sign-in…"}
        </div>
      </div>
    );
  }

  const visibleNav = NAV_ITEMS.filter(
    (item) => !item.minRole || hasRole(item.minRole)
  );
  const connected = backendStatus === "connected";

  return (
    <div className="min-h-screen bg-[color:var(--bg)] text-[color:var(--text)]">
      <div className="flex min-h-screen">
        {/* Sidebar */}
        <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col justify-between border-r border-[color:var(--glass-border)] bg-[color:var(--bg-raised)]/80 px-4 py-6 backdrop-blur-2xl lg:flex">
          <div>
            <div className="flex items-center gap-3 px-2">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[color:var(--accent-soft)] text-[color:var(--accent)]">
                <ShieldCheck className="h-5 w-5" />
              </span>
              <div>
                <p className="text-sm font-semibold tracking-wide text-slate-100">
                  SmartOps
                </p>
                <p className="text-[10px] uppercase tracking-widest text-slate-500">
                  Building Intelligence
                </p>
              </div>
            </div>

            <nav className="mt-8 space-y-1">
              {visibleNav.map((item) => {
                const active =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(item.href);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={classNames(
                      "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
                      active
                        ? "bg-white/8 text-slate-50 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]"
                        : "text-slate-400 hover:bg-white/4 hover:text-slate-200"
                    )}
                  >
                    <Icon
                      className={classNames(
                        "h-4 w-4 transition",
                        active
                          ? "text-[color:var(--accent)]"
                          : "text-slate-500 group-hover:text-slate-300"
                      )}
                    />
                    {item.name}
                    {active && (
                      <span className="ml-auto h-1.5 w-1.5 rounded-full bg-[color:var(--accent)]" />
                    )}
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="space-y-3">
            <div className="glass-panel flex items-center justify-between !rounded-2xl p-3">
              <div className="min-w-0">
                <Link href="/account" title="Account and password" className="block truncate text-sm font-semibold text-slate-200 hover:underline">
                  {user.name}
                </Link>
                <p className="text-[10px] uppercase tracking-widest text-[color:var(--accent)]">
                  {user.role}
                </p>
              </div>
              <button
                onClick={() => {
                  logout();
                  router.replace("/login");
                }}
                title="Sign out"
                className="rounded-lg p-2 text-slate-500 transition hover:bg-white/5 hover:text-slate-200"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
            <p className="px-2 text-[10px] leading-relaxed text-slate-600">
              <Link href="/privacy" className="underline decoration-dotted hover:text-slate-400">How SmartOps handles data</Link>:
              no face or identity recognition, evidence restricted by default.
            </p>
          </div>
        </aside>

        {/* Main column */}
        <div className="flex flex-1 flex-col lg:pl-60">
          <header className="sticky top-0 z-20 border-b border-[color:var(--glass-border)] bg-[color:var(--bg)]/70 px-6 py-3.5 backdrop-blur-2xl">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex min-w-0 flex-1 items-center gap-3">
                <WorkspaceBadge enabled={Boolean(user)} />
                <span
                  className={classNames(
                    "inline-flex items-center gap-2 rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide",
                    connected
                      ? "bg-[color:var(--accent-soft)] text-[color:var(--accent)]"
                      : "bg-amber-400/10 text-amber-300"
                  )}
                >
                  <span
                    className={classNames(
                      "h-1.5 w-1.5 rounded-full",
                      connected
                        ? "pulse-dot bg-[color:var(--accent)]"
                        : "bg-amber-300"
                    )}
                  />
                  {connected ? "Connected" : backendStatus === "loading" ? "Connecting" : "Offline"}
                </span>
                <p className="hidden truncate text-xs text-slate-500 md:block">
                  {connected && runtime
                    ? `${runtime.activeSourceCount}/${runtime.totalSourceCount} sources active · ${runtime.modelProvider} · ${runtime.orchestrator}`
                    : "Waiting for the API and live updates"}
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={selectedBuildingId}
                  onChange={(event) => setSelectedBuildingId(event.target.value)}
                  className="rounded-xl border border-[color:var(--glass-border)] bg-white/5 px-3 py-2 text-xs font-semibold text-slate-200 backdrop-blur focus-visible:outline-none"
                >
                  {buildings.map((building) => (
                    <option key={building.id} value={building.id}>
                      {building.name}
                    </option>
                  ))}
                </select>
                <select
                  value={timeRange}
                  onChange={(event) =>
                    setTimeRange(
                      event.target.value as keyof typeof TIME_RANGE_LABELS
                    )
                  }
                  className="rounded-xl border border-[color:var(--glass-border)] bg-white/5 px-3 py-2 text-xs font-semibold text-slate-200 backdrop-blur focus-visible:outline-none"
                >
                  {Object.entries(TIME_RANGE_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
                <div className="hidden items-center gap-2 rounded-xl border border-[color:var(--glass-border)] bg-white/5 px-3 py-2 text-xs text-slate-400 backdrop-blur focus-within:border-[color:var(--accent)]/40 md:flex">
                  <Search className="h-3.5 w-3.5" />
                  <input
                    value={searchQuery}
                    onChange={(event) => setSearchQuery(event.target.value)}
                    placeholder="Search events, zones, sources"
                    aria-label="Search events"
                    className="w-44 bg-transparent text-xs text-slate-200 focus:outline-none"
                  />
                </div>
              </div>
            </div>

            <nav className="mt-3 flex gap-1.5 overflow-x-auto lg:hidden">
              {visibleNav.map((item) => {
                const active =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={classNames(
                      "whitespace-nowrap rounded-full px-3.5 py-1.5 text-xs font-semibold transition",
                      active
                        ? "bg-[color:var(--accent-soft)] text-[color:var(--accent)]"
                        : "bg-white/5 text-slate-400"
                    )}
                  >
                    {item.name}
                  </Link>
                );
              })}
            </nav>
          </header>

          <main className="flex-1 px-6 py-6">
            {actionError && <div role="alert" className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">{actionError}</div>}
            {backendStatus === "connected" && <DegradedBanner />}
            {backendStatus === "loading" ? <SkeletonPanel lines={6} /> : backendStatus === "offline" ? (
              <ErrorState title="Live connection unavailable" description="The API or event stream is unreachable. Data and actions are unavailable while SmartOps reconnects automatically." />
            ) : children}
          </main>
        </div>
      </div>
    </div>
  );
};
