import type { ReactNode } from "react";

import { cn } from "../internal/cn";

type BadgeTone = "neutral" | "primary" | "success" | "warning" | "danger";

const tones: Record<BadgeTone, string> = {
  neutral: "border-line bg-surface-subtle text-muted-strong",
  primary: "bg-primary-soft text-primary-strong",
  success: "bg-success-soft text-success-strong",
  warning: "bg-warning-soft text-warning-strong",
  danger: "bg-danger-soft text-danger",
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
        "inline-flex min-h-6 items-center gap-1 rounded-full border border-transparent px-2.5 py-0.5 text-[0.6875rem] font-bold leading-5",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
