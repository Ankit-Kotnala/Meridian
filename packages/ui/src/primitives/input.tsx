import { forwardRef, type InputHTMLAttributes } from "react";

import { cn } from "../internal/cn";

export const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement>
>(function Input({ className, ...props }, ref) {
  return (
    <input
      className={cn(
        "min-h-11 w-full rounded-[var(--radius-control)] border border-line-strong bg-white px-3.5 text-sm text-foreground shadow-sm outline-none placeholder:text-muted",
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
