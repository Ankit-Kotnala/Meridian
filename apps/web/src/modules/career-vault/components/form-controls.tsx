import { forwardRef, type ReactNode, type TextareaHTMLAttributes } from "react";

import { cn } from "@careeros/ui";

import type { FieldErrors } from "../validation/career-vault-validation";

export const FieldErrorSummary = forwardRef<
  HTMLDivElement,
  { errors: FieldErrors; title?: string }
>(function FieldErrorSummary(
  { errors, title = "Review the highlighted fields" },
  ref,
) {
  const messages = Array.from(new Set(Object.values(errors)));
  if (messages.length === 0) return null;
  return (
    <div
      className="mb-5 rounded-xl border border-red-200 bg-danger-soft p-4 text-sm text-danger"
      ref={ref}
      role="alert"
      tabIndex={-1}
    >
      <p className="font-extrabold">{title}</p>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        {messages.map((message) => (
          <li key={message}>{message}</li>
        ))}
      </ul>
    </div>
  );
});

export function TextareaField({
  error,
  hint,
  id,
  label,
  className,
  ...props
}: Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id"> & {
  error?: string | undefined;
  hint?: ReactNode;
  id: string;
  label: ReactNode;
}) {
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  return (
    <div className="space-y-2">
      <label className="block text-sm font-bold text-foreground" htmlFor={id}>
        {label}
      </label>
      <textarea
        aria-describedby={describedBy}
        aria-invalid={Boolean(error)}
        className={cn(
          "min-h-28 w-full resize-y rounded-xl border border-line bg-white px-3.5 py-3 text-sm leading-6 text-foreground shadow-sm outline-none",
          "hover:border-slate-300 focus:border-primary focus:ring-3 focus:ring-primary-soft",
          "aria-[invalid=true]:border-danger aria-[invalid=true]:focus:ring-danger-soft",
          className,
        )}
        id={id}
        {...props}
      />
      {hint && (
        <div className="text-xs leading-5 text-muted" id={hintId}>
          {hint}
        </div>
      )}
      {error && (
        <p className="text-xs font-semibold text-danger" id={errorId}>
          {error}
        </p>
      )}
    </div>
  );
}
