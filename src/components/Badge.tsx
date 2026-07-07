import { CSSProperties } from "react";
import { classNames } from "@/lib/utils";

const toneStyles: Record<string, string> = {
  green: "bg-emerald-500/20 text-emerald-200",
  amber: "bg-amber-500/20 text-amber-200",
  red: "bg-rose-500/20 text-rose-200",
  blue: "bg-sky-500/20 text-sky-200",
  slate: "bg-slate-700/60 text-slate-200",
};

export const Badge = ({
  label,
  tone = "slate",
  className,
  style,
}: {
  label: string;
  tone?: keyof typeof toneStyles;
  className?: string;
  style?: CSSProperties;
}) => (
  <span
    className={classNames(
      "inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide",
      toneStyles[tone],
      className
    )}
    style={style}
  >
    {label}
  </span>
);





