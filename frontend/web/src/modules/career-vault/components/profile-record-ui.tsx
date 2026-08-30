"use client";

import { CheckCircle2, CircleAlert, MoreVertical } from "lucide-react";
import {
  useEffect,
  useRef,
  useState,
  type HTMLAttributes,
  type ReactNode,
} from "react";

import { Card, cn } from "@rezumi/ui";

/**
 * Presentation primitives shared by every Career Profile record table.
 *
 * The profile is a set of typed record collections that all read the same way:
 * a titled panel, a dense table, an explicit confirmation state, and a row menu
 * for the destructive or reordering actions that should not sit in the row
 * itself. Keeping that shape here stops each section from drifting.
 */

export function ProfilePanel({
  action,
  allowOverflow = false,
  children,
  id,
  title,
}: {
  action?: ReactNode;
  /** Set when the panel body anchors a popover that has to escape the card. */
  allowOverflow?: boolean;
  children: ReactNode;
  id: string;
  title: string;
}) {
  return (
    <section
      aria-labelledby={`${id}-heading`}
      className="scroll-mt-[8.25rem]"
      id={id}
    >
      <Card className={allowOverflow ? undefined : "overflow-hidden"}>
        <header className="flex min-h-[3.375rem] flex-wrap items-center justify-between gap-3 border-b border-line bg-surface-subtle/55 px-4 py-2.5 sm:px-5">
          <h2
            className="text-[0.9375rem] font-bold tracking-[-0.01em] text-foreground"
            id={`${id}-heading`}
          >
            {title}
          </h2>
          {action}
        </header>
        {children}
      </Card>
    </section>
  );
}

export type RecordColumn = {
  className?: string;
  key: string;
  label: string;
  srOnly?: boolean;
};

export function RecordTable({
  children,
  columns,
}: {
  children: ReactNode;
  columns: readonly RecordColumn[];
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[40rem] border-collapse text-left">
        <thead>
          <tr className="border-b border-line">
            {columns.map((column) => (
              <th
                className={cn(
                  "px-4 py-2 text-[0.75rem] font-semibold text-muted",
                  column.className,
                )}
                key={column.key}
                scope="col"
              >
                <span className={column.srOnly ? "sr-only" : undefined}>
                  {column.label}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        {children}
      </table>
    </div>
  );
}

export function RecordRow({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn(
        "border-b border-line/70 last:border-b-0 hover:bg-surface-subtle/45",
        className,
      )}
      {...props}
    >
      {children}
    </tr>
  );
}

export function RecordCell({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <td className={cn("px-4 py-2.5 align-middle text-[0.8125rem]", className)}>
      {children}
    </td>
  );
}

export function EmptyRecordRow({
  children,
  colSpan,
}: {
  children: ReactNode;
  colSpan: number;
}) {
  return (
    <tr>
      <td
        className="px-4 py-8 text-center text-[0.8125rem] text-muted"
        colSpan={colSpan}
      >
        {children}
      </td>
    </tr>
  );
}

export function ConfirmationStatus({ confirmed }: { confirmed: boolean }) {
  return confirmed ? (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-[0.8125rem] font-semibold text-success-strong">
      <CheckCircle2 aria-hidden="true" className="size-4 shrink-0" />
      Confirmed
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-[0.8125rem] font-semibold text-warning-strong">
      <CircleAlert aria-hidden="true" className="size-4 shrink-0" />
      Needs review
    </span>
  );
}

export function RowLink({
  children,
  expanded,
  label,
  onClick,
}: {
  children: ReactNode;
  expanded?: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      aria-label={label}
      {...(expanded === undefined ? {} : { "aria-expanded": expanded })}
      className="inline-flex items-center gap-1 whitespace-nowrap text-[0.8125rem] font-semibold text-info hover:text-info-strong hover:underline"
      onClick={onClick}
      type="button"
    >
      {children}
    </button>
  );
}

export function IconAction({
  disabled = false,
  icon: Icon,
  label,
  onClick,
  tone = "muted",
}: {
  disabled?: boolean;
  icon: typeof CheckCircle2;
  label: string;
  onClick: () => void;
  tone?: "danger" | "muted";
}) {
  return (
    <button
      aria-label={label}
      className={cn(
        "grid size-8 shrink-0 place-items-center rounded-[var(--radius-control)] transition-colors disabled:cursor-not-allowed disabled:opacity-45",
        tone === "danger"
          ? "text-muted hover:bg-danger-soft hover:text-danger"
          : "text-muted hover:bg-surface-inset hover:text-foreground",
      )}
      disabled={disabled}
      onClick={onClick}
      title={label}
      type="button"
    >
      <Icon aria-hidden="true" className="size-4" />
    </button>
  );
}

export type RowMenuItem = {
  disabled?: boolean;
  label: string;
  onSelect: () => void;
  tone?: "danger";
};

export function RowMenu({
  items,
  label,
}: {
  items: readonly RowMenuItem[];
  label: string;
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(event: PointerEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setOpen(false);
      triggerRef.current?.focus();
    }
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  if (items.length === 0) return null;

  return (
    <div className="relative" ref={containerRef}>
      <button
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={label}
        className="grid size-8 shrink-0 place-items-center rounded-[var(--radius-control)] text-muted transition-colors hover:bg-surface-inset hover:text-foreground"
        onClick={() => setOpen((value) => !value)}
        ref={triggerRef}
        title={label}
        type="button"
      >
        <MoreVertical aria-hidden="true" className="size-4" />
      </button>
      {open && (
        <div
          aria-label={label}
          className="absolute right-0 top-9 z-20 w-56 overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface p-1 shadow-[var(--shadow-lg)]"
          role="menu"
        >
          {items.map((item) => (
            <button
              className={cn(
                "flex min-h-9 w-full items-center rounded-[var(--radius-control)] px-3 text-left text-[0.8125rem] font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-45",
                item.tone === "danger"
                  ? "text-danger hover:bg-danger-soft"
                  : "text-foreground hover:bg-surface-subtle",
              )}
              disabled={item.disabled ?? false}
              key={item.label}
              onClick={() => {
                setOpen(false);
                item.onSelect();
              }}
              role="menuitem"
              type="button"
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function DetailRow({
  children,
  colSpan,
}: {
  children: ReactNode;
  colSpan: number;
}) {
  return (
    <tr className="border-b border-line/70 bg-surface-subtle/40">
      <td className="px-4 py-4 sm:px-6" colSpan={colSpan}>
        {children}
      </td>
    </tr>
  );
}

export function DetailField({
  children,
  label,
}: {
  children: ReactNode;
  label: string;
}) {
  return (
    <div>
      <dt className="text-[0.6875rem] font-bold uppercase tracking-[0.06em] text-muted">
        {label}
      </dt>
      <dd className="mt-1 whitespace-pre-wrap text-[0.8125rem] leading-6 text-foreground">
        {children}
      </dd>
    </div>
  );
}

/**
 * Provenance is shown as a single readable source label in the table so the row
 * stays scannable; the full span-level provenance stays one click away in the
 * expanded record detail.
 */
export function provenanceSummary(
  values: readonly { sourceLabel: string; sourceType: string }[],
): string {
  const first = values[0];
  if (!first) return "Manual";
  if (first.sourceType === "manual") return "Manual";
  return first.sourceLabel || first.sourceType;
}
