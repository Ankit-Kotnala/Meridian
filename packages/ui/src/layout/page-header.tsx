import type { ReactNode } from "react";

import { cn } from "../internal/cn";

export function PageHeader({
  actions,
  className,
  description,
  eyebrow,
  id,
  metadata,
  title,
}: {
  actions?: ReactNode;
  className?: string;
  description?: ReactNode;
  eyebrow?: ReactNode;
  id?: string;
  metadata?: ReactNode;
  title: ReactNode;
}) {
  return (
    <header
      className={cn(
        "relative mb-7 grid gap-5 border-b border-line pb-6 before:absolute before:-bottom-px before:left-0 before:h-px before:w-16 before:bg-primary sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end",
        className,
      )}
    >
      <div className="min-w-0">
        {eyebrow && <div className="eyebrow mb-2">{eyebrow}</div>}
        <h1
          className="font-display text-2xl font-semibold leading-tight tracking-[-0.03em] text-foreground sm:text-[2rem]"
          id={id}
        >
          {title}
        </h1>
        {description && (
          <div className="mt-2 max-w-3xl text-sm leading-6 text-muted sm:text-[0.9375rem]">
            {description}
          </div>
        )}
        {metadata && <div className="mt-3">{metadata}</div>}
      </div>
      {actions && (
        <div className="flex flex-wrap items-center gap-2 sm:justify-end">
          {actions}
        </div>
      )}
    </header>
  );
}

export function SectionHeader({
  actions,
  className,
  description,
  id,
  title,
}: {
  actions?: ReactNode;
  className?: string;
  description?: ReactNode;
  id?: string;
  title: ReactNode;
}) {
  return (
    <header
      className={cn(
        "mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between",
        className,
      )}
    >
      <div className="min-w-0">
        <h2
          className="text-lg font-semibold tracking-[-0.02em] text-foreground"
          id={id}
        >
          {title}
        </h2>
        {description && (
          <div className="mt-1 max-w-3xl text-sm leading-6 text-muted">
            {description}
          </div>
        )}
      </div>
      {actions && (
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {actions}
        </div>
      )}
    </header>
  );
}
