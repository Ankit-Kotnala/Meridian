"use client";

import { useId, useState, type KeyboardEvent, type ReactNode } from "react";

import { cn } from "../internal/cn";

export type TabItem = {
  id: string;
  label: string;
  panel: ReactNode;
};

export function Tabs({
  className,
  defaultValue,
  label,
  onValueChange,
  tabs,
  value,
  variant = "default",
}: {
  className?: string;
  defaultValue?: string;
  label: string;
  onValueChange?: (value: string) => void;
  tabs: readonly TabItem[];
  value?: string;
  /**
   * `section` matches the workspace sub-navigation: a full-bleed bar with its
   * labels aligned to the page content below it. It expects to be the first
   * thing inside a page container carrying the standard page gutter
   * (`--space-page-inline` / `--space-page-block`), which it cancels with
   * negative margins so the bar reaches the edges the way the sub-navigation
   * above `<main>` does.
   */
  variant?: "default" | "section";
}) {
  const prefix = useId();
  const [internalValue, setInternalValue] = useState(
    defaultValue ?? tabs[0]?.id ?? "",
  );
  const active = value ?? internalValue;
  const isSection = variant === "section";

  function select(next: string) {
    if (value === undefined) setInternalValue(next);
    onValueChange?.(next);
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (!new Set(["ArrowLeft", "ArrowRight", "Home", "End"]).has(event.key))
      return;
    event.preventDefault();
    const current = Math.max(
      0,
      tabs.findIndex((tab) => tab.id === active),
    );
    const target =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? tabs.length - 1
          : event.key === "ArrowRight"
            ? (current + 1) % tabs.length
            : (current - 1 + tabs.length) % tabs.length;
    const next = tabs[target];
    if (!next) return;
    select(next.id);
    document.getElementById(`${prefix}-tab-${next.id}`)?.focus();
  }

  const tablist = (
    <div
      aria-label={label}
      className={cn(
        // `scroll-strip` keeps the strip scrollable without painting a
        // scrollbar next to the last tab - see the rule in globals.css.
        "flex overflow-x-auto scroll-strip",
        isSection
          ? "mx-auto w-full max-w-[var(--content-wide)] gap-6 px-[var(--space-page-inline)]"
          : "gap-5 border-b border-line",
      )}
      onKeyDown={onKeyDown}
      role="tablist"
    >
      {tabs.map((tab) => {
        const selected = tab.id === active;
        return (
          <button
            aria-controls={`${prefix}-panel-${tab.id}`}
            aria-selected={selected}
            className={cn(
              "shrink-0 border-b-2 transition-colors",
              isSection
                ? "-mb-px flex min-h-11 items-center text-[0.8125rem] font-semibold"
                : "min-h-11 px-0.5 text-sm font-bold",
              selected
                ? isSection
                  ? "border-info text-info"
                  : "border-primary text-primary"
                : cn(
                    "border-transparent text-muted hover:text-foreground",
                    isSection && "hover:border-line-strong",
                  ),
            )}
            id={`${prefix}-tab-${tab.id}`}
            key={tab.id}
            onClick={() => select(tab.id)}
            role="tab"
            tabIndex={selected ? 0 : -1}
            type="button"
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );

  return (
    <div className={className}>
      {isSection ? (
        <div className="-mx-[var(--space-page-inline)] -mt-[var(--space-page-block)] mb-6 border-b border-line bg-surface">
          {tablist}
        </div>
      ) : (
        tablist
      )}
      {tabs.map((tab) => (
        <div
          aria-labelledby={`${prefix}-tab-${tab.id}`}
          hidden={tab.id !== active}
          id={`${prefix}-panel-${tab.id}`}
          key={tab.id}
          role="tabpanel"
          tabIndex={0}
        >
          {tab.panel}
        </div>
      ))}
    </div>
  );
}
