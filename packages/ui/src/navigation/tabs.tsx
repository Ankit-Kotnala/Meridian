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
}: {
  className?: string;
  defaultValue?: string;
  label: string;
  onValueChange?: (value: string) => void;
  tabs: readonly TabItem[];
  value?: string;
}) {
  const prefix = useId();
  const [internalValue, setInternalValue] = useState(
    defaultValue ?? tabs[0]?.id ?? "",
  );
  const active = value ?? internalValue;

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

  return (
    <div className={className}>
      <div
        aria-label={label}
        className="flex gap-5 overflow-x-auto border-b border-line"
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
                "min-h-11 shrink-0 border-b-2 px-0.5 text-sm font-bold transition-colors",
                selected
                  ? "border-primary text-primary"
                  : "border-transparent text-muted hover:text-foreground",
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
