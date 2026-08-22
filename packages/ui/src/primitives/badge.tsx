import type { ReactNode } from "react";

import { cn } from "../internal/cn";

type BadgeTone = "neutral" | "primary" | "success" | "warning" | "danger";

const tones: Record<BadgeTone, string> = {
  neutral:
    "border border-line bg-surface-subtle/80 text-muted-strong",
  primary:
    "border border-primary/12 bg-primary-soft text-primary-strong",
  success:
    "border border-success/15 bg-success-soft text-success-strong",
  warning:
    "border border-warning/18 bg-warning-soft text-warning-strong",
  danger: "border border-danger/15 bg-danger-soft text-danger-strong",
};

export function Badge({
  children,
  className,
  tone = "neutral",
}: {
  children: ReactNode;
  className?: string;
  tone?: BadgeTone;
}) {
  return (
    <span
      className={cn(
        "inline-flex min-h-[1.375rem] items-center gap-1 rounded-[var(--radius-pill)] px-2.5 py-0.5 text-[0.6875rem] font-semibold leading-5",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
