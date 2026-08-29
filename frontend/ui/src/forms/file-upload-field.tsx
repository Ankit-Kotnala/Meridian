"use client";

import { FileText, UploadCloud, X } from "lucide-react";
import {
  useRef,
  type ChangeEvent,
  type DragEvent,
  type InputHTMLAttributes,
} from "react";

import { cn } from "../internal/cn";

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "Unknown size";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"] as const;
  let value = bytes / 1024;
  let unit: (typeof units)[number] = units[0];
  for (let index = 1; index < units.length && value >= 1024; index += 1) {
    value /= 1024;
    unit = units[index]!;
  }
  return `${value < 10 ? value.toFixed(1) : Math.round(value)} ${unit}`;
}

export type FileUploadFieldProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "children" | "onChange" | "type" | "value"
> & {
  error?: string | undefined;
  hint?: string | undefined;
  label: string;
  onFileChange: (file: File | undefined) => void;
  selectedFile?: File | undefined;
};

export function FileUploadField({
  accept,
  className,
  disabled,
  error,
  hint,
  id,
  label,
  onFileChange,
  selectedFile,
  ...props
}: FileUploadFieldProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const errorId = error && id ? `${id}-error` : undefined;
  const hintId = hint && id ? `${id}-hint` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;

  function choose(event: ChangeEvent<HTMLInputElement>) {
    onFileChange(event.target.files?.[0]);
  }

  function drop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    if (disabled) return;
    onFileChange(event.dataTransfer.files[0]);
  }

  function clear() {
    if (inputRef.current) inputRef.current.value = "";
    onFileChange(undefined);
  }

  return (
    <div className={cn("space-y-2", className)}>
      <label className="block text-sm font-bold text-foreground" htmlFor={id}>
        {label}
      </label>
      {selectedFile ? (
        <div className="flex min-h-24 items-center gap-3 rounded-2xl border border-primary/30 bg-primary-soft/35 p-4">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-surface text-primary shadow-sm">
            <FileText aria-hidden="true" className="size-5" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-extrabold text-foreground">
              {selectedFile.name}
            </p>
            <p className="mt-1 text-xs text-muted">
              {formatBytes(selectedFile.size)}
              {selectedFile.type ? ` · ${selectedFile.type}` : ""}
            </p>
          </div>
          <button
            aria-label={`Remove ${selectedFile.name}`}
            className="grid size-10 shrink-0 place-items-center rounded-xl text-muted transition hover:bg-surface hover:text-foreground"
            disabled={disabled}
            onClick={clear}
            type="button"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>
      ) : (
        <div
          className={cn(
            "group relative grid min-h-44 place-items-center rounded-2xl border-2 border-dashed border-line bg-surface p-6 text-center transition hover:border-primary/45 hover:bg-primary-soft/20 focus-within:border-primary focus-within:ring-3 focus-within:ring-primary/20",
            disabled && "cursor-not-allowed opacity-55",
            error && "border-danger/60 bg-danger-soft/25",
          )}
          onDragOver={(event) => event.preventDefault()}
          onDrop={drop}
        >
          <input
            {...props}
            accept={accept}
            aria-describedby={describedBy}
            aria-invalid={Boolean(error)}
            className="absolute inset-0 size-full cursor-pointer opacity-0 disabled:cursor-not-allowed"
            disabled={disabled}
            id={id}
            onChange={choose}
            ref={inputRef}
            type="file"
          />
          <div aria-hidden="true" className="pointer-events-none">
            <span className="mx-auto grid size-12 place-items-center rounded-xl bg-primary-soft text-primary">
              <UploadCloud className="size-5" />
            </span>
            <p className="mt-4 text-sm font-extrabold text-foreground">
              Choose a file or drop it here
            </p>
            <p className="mt-1 text-xs leading-5 text-muted">
              PDF or DOCX. The server verifies the actual file contents.
            </p>
          </div>
        </div>
      )}
      {hint && (
        <p className="text-xs leading-5 text-muted" id={hintId}>
          {hint}
        </p>
      )}
      {error && (
        <p className="text-xs font-semibold leading-5 text-danger" id={errorId}>
          {error}
        </p>
      )}
    </div>
  );
}

export { formatBytes };
