import type { ReactNode } from "react";

import { cn } from "../internal/cn";

export function DefinitionList({
  className,
  items,
}: {
  className?: string;
  items: ReadonlyArray<{ label: ReactNode; value: ReactNode }>;
}) {
  return (
    <dl
      className={cn(
        "grid divide-y divide-line rounded-[var(--radius-control)] border border-line bg-surface",
        className,
      )}
    >
      {items.map((item, index) => (
        <div
          className="grid gap-1 px-4 py-3 sm:grid-cols-[10rem_minmax(0,1fr)] sm:gap-5"
          key={index}
        >
          <dt className="text-xs font-bold text-muted-strong">{item.label}</dt>
          <dd className="min-w-0 text-sm text-foreground">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
