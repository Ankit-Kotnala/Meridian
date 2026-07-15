import type { ReactNode } from "react";

import { cn } from "../internal/cn";

type BadgeTone = "neutral" | "primary" | "success" | "warning" | "danger";

const tones: Record<BadgeTone, string> = {
  neutral: "bg-slate-100 text-slate-600",
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
        "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[0.68rem] font-bold",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
