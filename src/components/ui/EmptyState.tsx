import { ReactNode } from "react";
import { Inbox } from "lucide-react";

export const EmptyState = ({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) => (
  <div className="glass-panel flex flex-col items-center gap-3 px-6 py-14 text-center">
    <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/5 text-slate-500">
      {icon ?? <Inbox className="h-5 w-5" />}
    </span>
    <p className="text-sm font-semibold text-slate-200">{title}</p>
    {description && (
      <p className="max-w-md text-xs leading-relaxed text-slate-500">{description}</p>
    )}
    {action}
  </div>
);

export const ErrorState = ({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) => (
  <div className="glass-panel flex flex-col items-center gap-3 border-rose-500/25 px-6 py-14 text-center">
    <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-rose-500/10 text-rose-300">
      !
    </span>
    <p className="text-sm font-semibold text-rose-200">{title}</p>
    {description && (
      <p className="max-w-md text-xs leading-relaxed text-slate-500">{description}</p>
    )}
    {action}
  </div>
);
