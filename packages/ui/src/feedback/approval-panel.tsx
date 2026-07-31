import { ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "../internal/cn";

export function ApprovalPanel({
  actions,
  children,
  className,
  evidence,
  title,
}: {
  actions: ReactNode;
  children: ReactNode;
  className?: string;
  evidence?: ReactNode;
  title: ReactNode;
}) {
  return (
    <section
      className={cn(
        "overflow-hidden rounded-[var(--radius-card)] border border-primary/30 bg-primary-soft",
        className,
      )}
    >
      <div className="flex items-start gap-3 p-4 sm:p-5">
        <ShieldCheck
          aria-hidden="true"
          className="mt-0.5 size-5 shrink-0 text-primary"
        />
        <div className="min-w-0">
          <h2 className="font-semibold text-foreground">{title}</h2>
          <div className="mt-1 text-sm leading-6 text-muted-strong">
            {children}
          </div>
          {evidence && (
            <div className="mt-3 border-l-2 border-primary/35 pl-3 text-xs leading-5 text-muted">
              {evidence}
            </div>
          )}
        </div>
      </div>
      <div className="flex flex-wrap gap-2 border-t border-primary/20 bg-surface px-4 py-3 sm:px-5">
        {actions}
      </div>
    </section>
  );
}
