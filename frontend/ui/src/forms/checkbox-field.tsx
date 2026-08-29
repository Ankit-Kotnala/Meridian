import { forwardRef, type InputHTMLAttributes, type ReactNode } from "react";

import { cn } from "../internal/cn";

type CheckboxFieldProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "id" | "type"
> & {
  description?: ReactNode;
  error?: string | undefined;
  id: string;
  label: ReactNode;
};

export const CheckboxField = forwardRef<HTMLInputElement, CheckboxFieldProps>(
  function CheckboxField(
    { className, description, error, id, label, ...props },
    ref,
  ) {
    const descriptionId = description ? `${id}-description` : undefined;
    const errorId = error ? `${id}-error` : undefined;
    const describedBy =
      [descriptionId, errorId].filter(Boolean).join(" ") || undefined;

    return (
      <div>
        <div
          className={cn(
            "flex min-h-11 items-start gap-3 rounded-xl border border-line bg-surface p-3.5 text-sm text-foreground",
            error && "border-danger",
            className,
          )}
        >
          <input
            aria-describedby={describedBy}
            aria-invalid={Boolean(error)}
            className="mt-0.5 size-4 shrink-0 accent-primary"
            id={id}
            ref={ref}
            type="checkbox"
            {...props}
          />
          <span>
            <label className="font-bold" htmlFor={id}>
              {label}
            </label>
            {description && (
              <span
                className="mt-1 block text-xs leading-5 text-muted"
                id={descriptionId}
              >
                {description}
              </span>
            )}
          </span>
        </div>
        {error && (
          <p
            className="mt-2 text-xs font-semibold leading-5 text-danger"
            id={errorId}
          >
            {error}
          </p>
        )}
      </div>
    );
  },
);
