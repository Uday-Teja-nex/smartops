"use client";

import Link from "next/link";
import { ReactNode } from "react";
import { MiniSparkline } from "@/components/charts/MiniSparkline";
import { classNames } from "@/lib/utils";

const statusColors: Record<string, string> = {
  green: "bg-emerald-400",
  amber: "bg-amber-400",
  red: "bg-rose-500",
  blue: "bg-sky-400",
};

type Delta = {
  value: string;
  direction?: "up" | "down" | "flat";
  label?: string;
};

export const KpiCard = ({
  title,
  value,
  subtitle,
  helper,
  status,
  icon,
  delta,
  sparkline,
  progress,
  href,
  className,
}: {
  title: string;
  value: string;
  subtitle?: string;
  helper?: string;
  status?: keyof typeof statusColors;
  icon?: ReactNode;
  delta?: Delta;
  sparkline?: { data: number[]; color?: string };
  progress?: number;
  href?: string;
  className?: string;
}) => {
  const subtitleText = subtitle ?? helper;
  const progressValue =
    typeof progress === "number" ? Math.min(Math.max(progress, 0), 1) : null;
  const ringStyle =
    progressValue === null
      ? undefined
      : {
          background: `conic-gradient(#10b981 ${progressValue * 360}deg, #1f2937 0deg)`,
        };

  const content = (
    <div
      className={classNames(
        "flex h-full flex-col justify-between rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/95 p-4 shadow-[0_22px_70px_-45px_rgba(2,6,23,0.85)] transition hover:-translate-y-0.5",
        className
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            {title}
          </p>
          <div className="mt-2 flex items-center gap-3">
            <p className="text-2xl font-semibold text-slate-100">{value}</p>
            {status ? (
              <span
                className={classNames(
                  "h-2.5 w-2.5 rounded-full",
                  statusColors[status]
                )}
                aria-hidden
              />
            ) : null}
          </div>
          {subtitleText ? (
            <p className="text-xs text-slate-400">{subtitleText}</p>
          ) : null}
        </div>
        {icon ? (
          <div className="rounded-xl bg-slate-800/70 p-2 text-slate-200">
            {icon}
          </div>
        ) : null}
      </div>

      <div className="mt-4 flex items-center justify-between gap-3">
        {delta ? (
          <div className="flex items-center gap-2 text-xs font-semibold">
            <span
              className={classNames(
                "rounded-full px-2 py-1",
                delta.direction === "down"
                  ? "bg-rose-500/20 text-rose-200"
                  : delta.direction === "up"
                    ? "bg-emerald-500/20 text-emerald-200"
                    : "bg-slate-700/70 text-slate-200"
              )}
            >
              {delta.value}
            </span>
            {delta.label ? (
              <span className="text-slate-400">{delta.label}</span>
            ) : null}
          </div>
        ) : null}

        {progressValue !== null ? (
          <div className="relative h-10 w-10 rounded-full" style={ringStyle}>
            <div className="absolute inset-1 rounded-full bg-[color:var(--surface)]" />
            <span className="absolute inset-0 flex items-center justify-center text-[10px] font-semibold text-slate-300">
              {Math.round(progressValue * 100)}%
            </span>
          </div>
        ) : null}

        {sparkline ? (
          <div className="h-10 w-24">
            <MiniSparkline data={sparkline.data} color={sparkline.color} />
          </div>
        ) : null}
      </div>
    </div>
  );

  if (href) {
    return (
      <Link
        href={href}
        className="group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
      >
        {content}
      </Link>
    );
  }

  return content;
};


