import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "../internal/cn";

export const buttonStyles = {
  base: "inline-flex min-h-10 items-center justify-center gap-2 rounded-[var(--radius-control)] px-4 text-sm font-bold transition-[background-color,border-color,color] duration-150 aria-disabled:cursor-not-allowed aria-disabled:opacity-60 disabled:cursor-not-allowed disabled:opacity-60",
  primary:
    "border border-primary bg-primary text-white hover:border-primary-strong hover:bg-primary-strong",
  secondary:
    "border border-line-strong bg-surface text-foreground hover:border-primary/50 hover:bg-primary-soft/50",
  ghost: "text-muted-strong hover:bg-surface-subtle hover:text-foreground",
  dark: "bg-navy text-white hover:bg-navy-hover",
  danger:
    "border border-danger bg-danger text-white hover:border-danger-strong hover:bg-danger-strong",
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
