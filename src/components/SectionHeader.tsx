import { ReactNode } from "react";

export const SectionHeader = ({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) => (
  <div className="flex flex-wrap items-center justify-between gap-3">
    <div>
      <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
      {subtitle ? (
        <p className="text-sm text-slate-400">{subtitle}</p>
      ) : null}
    </div>
    {action ? <div>{action}</div> : null}
  </div>
);






