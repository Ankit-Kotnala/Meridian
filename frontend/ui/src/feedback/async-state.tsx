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
        "grid min-h-56 place-items-center rounded-[var(--radius-card)] border border-dashed border-line-strong bg-surface-raised p-6 text-center sm:p-8",
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
        className="mx-auto mb-4 grid size-10 place-items-center rounded-[var(--radius-control)] bg-primary-soft text-primary"
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
        className="mx-auto mb-4 grid size-10 place-items-center rounded-[var(--radius-control)] bg-danger-soft text-danger"
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

export function LoadingSkeleton({
  className,
  variant = "page",
}: {
  className?: string;
  variant?: "form" | "list" | "page" | "table";
}) {
  const rows = variant === "form" ? 3 : variant === "table" ? 5 : 4;
  return (
    <div
      aria-busy="true"
      aria-live="polite"
      className={cn("space-y-5", className)}
      role="status"
    >
      <span className="sr-only">Loading content</span>
      <div className="h-7 w-52 animate-pulse rounded-md bg-surface-inset" />
      <div className={cn("grid gap-3", variant === "page" && "md:grid-cols-2")}>
        {Array.from({ length: rows }, (_, index) => (
          <div
            className={cn(
              "animate-pulse rounded-[var(--radius-card)] border border-line bg-surface p-5",
              variant === "form" ? "h-20" : "h-24",
            )}
            key={index}
          >
            <div className="h-3 w-28 rounded bg-surface-inset" />
            <div className="mt-4 h-3 w-3/4 rounded bg-surface-subtle" />
            {variant !== "form" && (
              <div className="mt-3 h-3 w-1/2 rounded bg-surface-subtle" />
            )}
          </div>
        ))}
      </div>
      {variant === "page" && (
        <div className="h-52 animate-pulse rounded-[var(--radius-card)] border border-line bg-surface" />
      )}
    </div>
  );
}
