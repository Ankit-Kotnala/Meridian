import { forwardRef, type SelectHTMLAttributes } from "react";

import { cn } from "../internal/cn";

export const Select = forwardRef<
  HTMLSelectElement,
  SelectHTMLAttributes<HTMLSelectElement>
>(function Select({ className, ...props }, ref) {
  return (
    <select
      className={cn(
        "min-h-11 w-full rounded-[var(--radius-control)] border border-line-strong bg-white px-3.5 text-sm text-foreground shadow-sm outline-none",
        "hover:border-primary/70 focus:border-primary focus:ring-3 focus:ring-primary-soft",
        "disabled:cursor-not-allowed disabled:bg-surface-subtle disabled:text-muted",
        "aria-[invalid=true]:border-danger aria-[invalid=true]:focus:border-danger aria-[invalid=true]:focus:ring-danger-soft",
        className,
      )}
      ref={ref}
      {...props}
    />
  );
});
