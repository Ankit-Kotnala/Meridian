import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "../internal/cn";

export const buttonStyles = {
  base: "inline-flex min-h-11 items-center justify-center gap-2 rounded-[var(--radius-control)] px-4 text-sm font-bold transition-[background-color,border-color,color,box-shadow,transform] duration-150 active:translate-y-px aria-disabled:cursor-not-allowed aria-disabled:opacity-60 aria-disabled:active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-60 disabled:active:translate-y-0",
  primary:
    "border border-primary bg-primary text-white shadow-[0_7px_18px_-10px_rgba(23,74,53,0.8)] hover:-translate-y-0.5 hover:border-primary-strong hover:bg-primary-strong hover:shadow-[0_12px_24px_-12px_rgba(23,74,53,0.72)]",
  secondary:
    "border border-line-strong bg-surface text-foreground shadow-sm hover:-translate-y-0.5 hover:border-primary/60 hover:bg-primary-soft/45 hover:shadow-[var(--shadow-md)]",
  ghost: "text-muted-strong hover:bg-surface-subtle hover:text-foreground",
  dark: "bg-navy text-white shadow-sm hover:-translate-y-0.5 hover:bg-navy-hover hover:shadow-[var(--shadow-md)]",
  danger:
    "border border-danger bg-danger text-white shadow-sm hover:border-danger-strong hover:bg-danger-strong",
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
