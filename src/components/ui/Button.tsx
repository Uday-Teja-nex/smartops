import { ButtonHTMLAttributes, ReactNode } from "react";
import { classNames } from "@/lib/utils";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "danger" | "outline";
  size?: "sm" | "md";
  icon?: ReactNode;
};

const VARIANTS: Record<NonNullable<ButtonProps["variant"]>, string> = {
  primary:
    "bg-[color:var(--accent-strong)] text-slate-950 hover:brightness-110 disabled:opacity-40",
  ghost:
    "bg-transparent text-slate-300 hover:bg-white/5 disabled:opacity-40",
  danger:
    "bg-rose-500/15 text-rose-300 hover:bg-rose-500/25 disabled:opacity-40",
  outline:
    "border border-[color:var(--glass-border-strong)] bg-white/5 text-slate-200 hover:bg-white/10 disabled:opacity-40",
};

const SIZES: Record<NonNullable<ButtonProps["size"]>, string> = {
  sm: "px-2.5 py-1.5 text-xs",
  md: "px-3.5 py-2 text-sm",
};

export const Button = ({
  variant = "outline",
  size = "md",
  icon,
  className,
  children,
  ...rest
}: ButtonProps) => (
  <button
    className={classNames(
      "inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition disabled:cursor-not-allowed",
      VARIANTS[variant],
      SIZES[size],
      className
    )}
    {...rest}
  >
    {icon}
    {children}
  </button>
);
