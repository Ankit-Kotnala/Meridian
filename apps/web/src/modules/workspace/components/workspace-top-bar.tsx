"use client";

import { ChevronDown, Menu, UserRound } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode, RefObject } from "react";

import type { WorkspaceViewer } from "./workspace-shell";
import { resolveWorkspaceContext } from "./workspace-navigation";

function initials(name: string): string {
  const value = name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
  return value || "CO";
}

export function WorkspaceTopBar({
  accountActions,
  menuButtonRef,
  onOpenMenu,
  viewer,
}: {
  accountActions: ReactNode;
  menuButtonRef: RefObject<HTMLButtonElement | null>;
  onOpenMenu: () => void;
  viewer: WorkspaceViewer;
}) {
  const context = resolveWorkspaceContext(usePathname());

  return (
    <header className="sticky top-0 z-30 flex min-h-16 items-center justify-between gap-4 border-b border-line bg-white/96 px-4 backdrop-blur-md sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <button
          aria-label="Open application navigation"
          className="grid size-11 shrink-0 place-items-center rounded-[var(--radius-control)] border border-line bg-white text-foreground shadow-sm lg:hidden"
          onClick={onOpenMenu}
          ref={menuButtonRef}
          type="button"
        >
          <Menu aria-hidden="true" className="size-5" />
        </button>
        <div className="min-w-0 leading-tight">
          <p className="truncate text-[0.6875rem] font-bold uppercase tracking-[0.09em] text-muted">
            {context.group}
          </p>
          <p className="mt-1 truncate text-sm font-semibold text-foreground">
            {context.label}
          </p>
        </div>
      </div>

      <details className="group relative">
        <summary
          aria-label={`Account menu for ${viewer.displayName}`}
          className="flex min-h-11 list-none items-center gap-2 rounded-[var(--radius-control)] px-1.5 text-left hover:bg-surface-subtle [&::-webkit-details-marker]:hidden"
        >
          <span className="sr-only">Account menu</span>
          <span className="grid size-8 place-items-center rounded-full border border-primary/20 bg-primary-soft text-[0.6875rem] font-bold text-primary-strong">
            {initials(viewer.displayName)}
          </span>
          <span className="hidden max-w-40 truncate text-xs font-semibold text-foreground sm:block">
            {viewer.displayName}
          </span>
          <ChevronDown
            aria-hidden="true"
            className="hidden size-3.5 text-muted transition-transform group-open:rotate-180 sm:block"
          />
        </summary>
        <div className="absolute right-0 mt-2 w-72 overflow-hidden rounded-[var(--radius-card)] border border-line bg-white shadow-[var(--shadow-md)]">
          <div className="border-b border-line px-4 py-3">
            <p className="truncate text-sm font-semibold text-foreground">
              {viewer.displayName}
            </p>
            <p className="mt-1 truncate text-xs text-muted">{viewer.email}</p>
          </div>
          <div className="p-2">
            <Link
              className="flex min-h-11 items-center gap-2 rounded-[var(--radius-control)] px-3 text-sm font-semibold text-foreground hover:bg-surface-subtle"
              href="/settings"
            >
              <UserRound aria-hidden="true" className="size-4" /> Account
              settings
            </Link>
            <div className="mt-1 border-t border-line pt-1">
              {accountActions}
            </div>
          </div>
        </div>
      </details>
    </header>
  );
}
