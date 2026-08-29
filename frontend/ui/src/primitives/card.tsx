import { createElement, type HTMLAttributes, type ReactNode } from "react";

import { cn } from "../internal/cn";

export function Card({
  as = "div",
  children,
  className,
  ...props
}: HTMLAttributes<HTMLElement> & {
  as?: "article" | "aside" | "div" | "section";
  children: ReactNode;
}) {
  return createElement(
    as,
    {
      className: cn("surface-card rounded-[var(--radius-card)]", className),
      ...props,
    },
    children,
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
    <header className="flex items-start justify-between gap-4 border-b border-line px-5 py-4 sm:px-6">
      <div>
        <h2 className="text-sm font-bold tracking-[-0.01em] text-foreground">
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
