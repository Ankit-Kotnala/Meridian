import { forwardRef, type InputHTMLAttributes, type ReactNode } from "react";

import { cn } from "../internal/cn";
import { Input } from "../primitives/input";

type TextFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, "id"> & {
  error?: string | undefined;
  hint?: ReactNode;
  id: string;
  label: ReactNode;
};

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(
  function TextField({ className, error, hint, id, label, ...props }, ref) {
    const hintId = hint ? `${id}-hint` : undefined;
    const errorId = error ? `${id}-error` : undefined;
    const describedBy =
      [hintId, errorId].filter(Boolean).join(" ") || undefined;

    return (
      <div className="space-y-2">
        <label className="block text-sm font-bold text-foreground" htmlFor={id}>
          {label}
        </label>
        <Input
          aria-describedby={describedBy}
          aria-invalid={Boolean(error)}
          className={className}
          id={id}
          ref={ref}
          {...props}
        />
        {hint && (
          <div className="text-xs leading-5 text-muted" id={hintId}>
            {hint}
          </div>
        )}
        {error && (
          <p
            className="text-xs font-semibold leading-5 text-danger"
            id={errorId}
          >
            {error}
          </p>
        )}
      </div>
    );
  },
);

export function FieldLabel({
  children,
  className,
  htmlFor,
}: {
  children: ReactNode;
  className?: string;
  htmlFor: string;
}) {
  return (
    <label
      className={cn("block text-sm font-bold text-foreground", className)}
      htmlFor={htmlFor}
    >
      {children}
    </label>
  );
}
