"use client";

import Link from "next/link";
import type { ReactNode } from "react";

export type ProfileGap = {
  /** Set when the gap is closed somewhere else in the product, e.g. Settings. */
  href: string | null;
  label: string;
  onSelect: (() => void) | null;
};

const usedFor = [
  "Auto-fill applications",
  "Tailor resumes",
  "Match jobs",
  "Generate interview prep",
];

function lastUpdatedLabel(value: string): string {
  const updated = new Date(value);
  if (Number.isNaN(updated.getTime())) return "Not recorded";
  const time = new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(updated);
  const now = new Date();
  const sameDay =
    updated.getFullYear() === now.getFullYear() &&
    updated.getMonth() === now.getMonth() &&
    updated.getDate() === now.getDate();
  if (sameDay) return `Today, ${time}`;
  return `${new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(updated)}, ${time}`;
}

function GapRow({ children }: { children: ReactNode }) {
  return (
    <span className="flex items-start gap-2 text-left text-[0.8125rem] font-semibold text-muted-strong">
      <span
        aria-hidden="true"
        className="mt-1.5 size-1.5 shrink-0 rounded-full bg-danger"
      />
      {children}
    </span>
  );
}

/**
 * Right rail summarising what the career record still needs and what the rest
 * of the product does with it. Every gap is actionable so the summary is a
 * route into the editor rather than a scold.
 */
export function ProfileStatusRail({
  completedCount,
  gaps,
  totalCount,
  updatedAt,
}: {
  completedCount: number;
  gaps: readonly ProfileGap[];
  totalCount: number;
  updatedAt: string;
}) {
  const percent =
    totalCount === 0 ? 0 : Math.round((completedCount / totalCount) * 100);

  return (
    <aside
      aria-labelledby="profile-status-heading"
      className="border-line lg:sticky lg:top-[8.5rem] lg:border-l lg:pl-6"
    >
      <h2
        className="text-[0.9375rem] font-bold text-foreground"
        id="profile-status-heading"
      >
        Profile status
      </h2>
      <p className="mt-3 text-[0.8125rem] font-bold text-foreground">
        {completedCount} / {totalCount}{" "}
        <span className="font-semibold text-muted">complete</span>
      </p>
      <div
        aria-hidden="true"
        className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-inset"
      >
        <div
          className="h-full rounded-full bg-info transition-[width] duration-300 motion-reduce:transition-none"
          style={{ width: `${percent}%` }}
        />
      </div>

      {gaps.length > 0 && (
        <>
          <h3 className="mt-6 text-[0.8125rem] font-bold text-foreground">
            Missing from profile
          </h3>
          <ul className="mt-2 space-y-1.5">
            {gaps.map((gap) => (
              <li key={gap.label}>
                {gap.href ? (
                  <Link className="hover:underline" href={gap.href}>
                    <GapRow>{gap.label}</GapRow>
                  </Link>
                ) : (
                  <button
                    className="hover:underline"
                    onClick={() => gap.onSelect?.()}
                    type="button"
                  >
                    <GapRow>{gap.label}</GapRow>
                  </button>
                )}
              </li>
            ))}
          </ul>
        </>
      )}

      <h3 className="mt-6 text-[0.8125rem] font-bold text-foreground">
        How profile data is used
      </h3>
      <p className="mt-2 text-[0.8125rem] leading-6 text-muted">
        This career record is the source of truth for your resumes, job
        applications, and preparation tools.
      </p>

      <h3 className="mt-5 text-[0.8125rem] font-bold text-foreground">
        Used to
      </h3>
      <ul className="mt-2 space-y-1 text-[0.8125rem] text-muted">
        {usedFor.map((entry) => (
          <li className="flex items-start gap-2" key={entry}>
            <span
              aria-hidden="true"
              className="mt-2 size-1 shrink-0 rounded-full bg-muted"
            />
            {entry}
          </li>
        ))}
      </ul>

      <p className="mt-6 text-xs text-muted">
        Last updated:{" "}
        <span className="font-semibold text-muted-strong">
          {lastUpdatedLabel(updatedAt)}
        </span>
      </p>
    </aside>
  );
}
