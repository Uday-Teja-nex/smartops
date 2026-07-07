"use client";

import { ReactNode } from "react";
import { SectionHeader } from "@/components/SectionHeader";
import { classNames } from "@/lib/utils";

export const ChartCard = ({
  title,
  subtitle,
  action,
  children,
  footer,
  className,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}) => (
  <div
    className={classNames(
      "rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/95 p-5 shadow-[0_22px_70px_-45px_rgba(2,6,23,0.85)]",
      className
    )}
  >
    <SectionHeader title={title} subtitle={subtitle} action={action} />
    <div className="mt-4 h-56">{children}</div>
    {footer ? <div className="mt-4 text-xs text-slate-400">{footer}</div> : null}
  </div>
);


