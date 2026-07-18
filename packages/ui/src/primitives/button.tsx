import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "../internal/cn";

export const buttonStyles = {
  base: "inline-flex min-h-10 items-center justify-center gap-2 rounded-xl px-4 text-sm font-bold transition duration-200 disabled:cursor-not-allowed disabled:opacity-55",
  primary:
    "bg-primary text-white shadow-[0_8px_24px_rgba(91,70,245,.24)] hover:bg-primary-strong",
  secondary:
    "border border-line bg-white text-foreground shadow-sm hover:border-primary/40 hover:bg-primary-soft/50",
  ghost: "text-muted hover:bg-slate-100 hover:text-foreground",
  dark: "bg-navy text-white hover:bg-navy-hover",
  danger:
    "bg-danger text-white shadow-[0_8px_24px_rgba(190,24,93,.18)] hover:bg-danger/90",
} as const;

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  loading?: boolean;
  loadingLabel?: string;
  variant?: keyof typeof buttonStyles;
};

export function Button({
  children,
  className,
  disabled,
  loading = false,
  loadingLabel = "Working…",
  type = "button",
  variant = "primary",
  ...props
}: ButtonProps) {
  return (
    <button
      aria-busy={loading || undefined}
      className={cn(buttonStyles.base, buttonStyles[variant], className)}
      disabled={disabled || loading}
      type={type}
      {...props}
    >
      {loading ? (
        <>
          <span
            aria-hidden="true"
            className="size-4 animate-spin rounded-full border-2 border-current border-r-transparent"
          />
          <span>{loadingLabel}</span>
        </>
      ) : (
        children
      )}
    </button>
  );
}
