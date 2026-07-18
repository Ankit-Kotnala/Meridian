import { forwardRef, type InputHTMLAttributes } from "react";

import { cn } from "../internal/cn";

export const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement>
>(function Input({ className, ...props }, ref) {
  return (
    <input
      className={cn(
        "min-h-11 w-full rounded-xl border border-line bg-white px-3.5 text-sm text-foreground shadow-sm outline-none placeholder:text-slate-400",
        "hover:border-slate-300 focus:border-primary focus:ring-3 focus:ring-primary-soft",
        "disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-muted",
        "aria-[invalid=true]:border-danger aria-[invalid=true]:focus:border-danger aria-[invalid=true]:focus:ring-danger-soft",
        className,
      )}
      ref={ref}
      {...props}
    />
  );
});
