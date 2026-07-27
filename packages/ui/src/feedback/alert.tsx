import {
  AlertCircle,
  CheckCircle2,
  Info,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "../internal/cn";

const tones = {
  danger: {
    icon: AlertCircle,
    style: "border-danger/25 bg-danger-soft text-danger-strong",
  },
  info: {
    icon: Info,
    style: "border-info/25 bg-info-soft text-info-strong",
  },
  success: {
    icon: CheckCircle2,
    style: "border-success/25 bg-success-soft text-success-strong",
  },
  warning: {
    icon: TriangleAlert,
    style: "border-warning/25 bg-warning-soft text-warning-strong",
  },
} satisfies Record<string, { icon: LucideIcon; style: string }>;

export function Alert({
  children,
  className,
  role,
  title,
  tone = "info",
  ...props
}: HTMLAttributes<HTMLDivElement> & {
  children?: ReactNode;
  title: ReactNode;
  tone?: keyof typeof tones;
}) {
  const { icon: Icon, style } = tones[tone];
  const resolvedRole = role ?? (tone === "danger" ? "alert" : "status");

  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-[var(--radius-control)] border p-3.5 text-sm",
        style,
        className,
      )}
      role={resolvedRole}
      {...props}
    >
      <Icon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0">
        <p className="font-extrabold">{title}</p>
        {children && (
          <div className="mt-1 leading-5 opacity-85">{children}</div>
        )}
      </div>
    </div>
  );
}
