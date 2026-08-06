"use client";

import { Eye, EyeOff } from "lucide-react";
import {
  forwardRef,
  useState,
  type InputHTMLAttributes,
  type ReactNode,
} from "react";

import { Input } from "@rezumi/ui";

type PasswordFieldProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "id" | "type"
> & {
  error?: string | undefined;
  hint?: ReactNode;
  id: string;
  label: ReactNode;
};

export const PasswordField = forwardRef<HTMLInputElement, PasswordFieldProps>(
  function PasswordField({ error, hint, id, label, ...props }, ref) {
    const [visible, setVisible] = useState(false);
    const hintId = hint ? `${id}-hint` : undefined;
    const errorId = error ? `${id}-error` : undefined;
    const describedBy =
      [hintId, errorId].filter(Boolean).join(" ") || undefined;

    return (
      <div className="space-y-2">
        <label className="block text-sm font-bold text-foreground" htmlFor={id}>
          {label}
        </label>
        <div className="relative">
          <Input
            aria-describedby={describedBy}
            aria-invalid={Boolean(error)}
            className="pr-12"
            id={id}
            ref={ref}
            type={visible ? "text" : "password"}
            {...props}
          />
          <button
            aria-label={visible ? "Hide password" : "Show password"}
            className="absolute right-1 top-1/2 grid size-9 -translate-y-1/2 place-items-center rounded-lg text-muted hover:bg-surface-subtle hover:text-foreground"
            onClick={() => setVisible((value) => !value)}
            type="button"
          >
            {visible ? (
              <EyeOff aria-hidden="true" className="size-4" />
            ) : (
              <Eye aria-hidden="true" className="size-4" />
            )}
          </button>
        </div>
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
