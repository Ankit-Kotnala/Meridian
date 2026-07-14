import { AlertTriangle, Inbox, RotateCcw } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "../internal/cn";
import { Button } from "../primitives/button";

type StateShellProps = {
  children: ReactNode;
  className?: string | undefined;
};

function StateShell({ children, className }: StateShellProps) {
  return (
    <div
      className={cn(
        "grid min-h-64 place-items-center rounded-2xl border border-line bg-white p-8 text-center",
        className,
      )}
    >
      <div className="max-w-sm">{children}</div>
    </div>
  );
}

export function EmptyState({
  title = "Nothing here yet",
  description = "New items will appear here when they are available.",
  action,
  className,
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <StateShell className={className}>
      <span
        aria-hidden="true"
        className="mx-auto mb-4 grid size-11 place-items-center rounded-xl bg-primary-soft text-primary"
      >
        <Inbox className="size-5" />
      </span>
      <h2 className="font-extrabold text-foreground">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-muted">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </StateShell>
  );
}

export function ErrorState({
  title = "We couldn’t load this view",
  description = "Try again. If the problem continues, return to the dashboard.",
  onRetry,
  className,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <StateShell className={className}>
      <span
        aria-hidden="true"
        className="mx-auto mb-4 grid size-11 place-items-center rounded-xl bg-danger-soft text-danger"
      >
        <AlertTriangle className="size-5" />
      </span>
      <h2 className="font-extrabold text-foreground">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-muted">{description}</p>
      {onRetry && (
        <Button className="mt-5" onClick={onRetry} variant="secondary">
          <RotateCcw aria-hidden="true" className="size-4" />
          Try again
        </Button>
      )}
    </StateShell>
  );
}

export function LoadingSkeleton({ className }: { className?: string }) {
  return (
    <div
      aria-busy="true"
      aria-live="polite"
      className={cn("space-y-5", className)}
      role="status"
    >
      <span className="sr-only">Loading content</span>
      <div className="h-8 w-56 animate-pulse rounded-lg bg-slate-200" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <div
            className="h-32 animate-pulse rounded-2xl border border-line bg-white p-5"
            key={index}
          >
            <div className="h-3 w-24 rounded bg-slate-200" />
            <div className="mt-5 h-8 w-16 rounded bg-slate-200" />
            <div className="mt-3 h-3 w-32 rounded bg-slate-100" />
          </div>
        ))}
      </div>
      <div className="h-72 animate-pulse rounded-2xl border border-line bg-white" />
    </div>
  );
}
