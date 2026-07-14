import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

export function Card({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLElement> & { children: ReactNode }) {
  return (
    <section className={cn("surface-card rounded-2xl", className)} {...props}>
      {children}
    </section>
  );
}

export function CardHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <header className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
      <div>
        <h2 className="text-sm font-extrabold tracking-[-0.01em] text-foreground">
          {title}
        </h2>
        {description && (
          <p className="mt-1 text-xs leading-5 text-muted">{description}</p>
        )}
      </div>
      {action}
    </header>
  );
}
