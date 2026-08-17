"use client";

import { ChevronDown, Menu, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode, RefObject } from "react";

import { corpIdFor } from "@/shared/identity/corp-id";
import { ThemeToggle } from "@/shared/theme/theme-toggle";

import type { WorkspaceViewer } from "./workspace-shell";
import {
  resolveWorkspaceContext,
  workspaceUtilityNavigation,
} from "./workspace-navigation";

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
  const corpId = corpIdFor(viewer.id);

  return (
    <header className="sticky top-0 z-30 flex min-h-16 items-center justify-between gap-4 border-b border-line/80 bg-surface/72 px-4 shadow-[0_1px_0_color-mix(in_srgb,var(--foreground)_4%,transparent)] backdrop-blur-xl backdrop-saturate-150 sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <button
          aria-label="Open application navigation"
          className="grid size-11 shrink-0 place-items-center rounded-[var(--radius-control)] border border-line bg-surface text-foreground shadow-sm transition-colors hover:border-primary/40 hover:bg-primary-soft/50 lg:hidden"
          onClick={onOpenMenu}
          ref={menuButtonRef}
          type="button"
        >
          <Menu aria-hidden="true" className="size-5" />
        </button>
        <div className="min-w-0 leading-tight">
          <p className="eyebrow truncate !text-[0.6875rem] tracking-[0.09em]">
            {context.group}
          </p>
          <p className="mt-0.5 truncate text-sm font-semibold text-foreground">
            {context.label}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-1.5">
        <ThemeToggle />

        <details className="group relative">
          <summary
            aria-label={`Account menu for ${viewer.displayName}`}
            className="flex min-h-11 list-none items-center gap-2 rounded-[var(--radius-control)] border border-transparent px-1.5 text-left transition-colors hover:border-line hover:bg-surface hover:shadow-sm [&::-webkit-details-marker]:hidden"
          >
            <span className="sr-only">Account menu</span>
            <span className="grid size-8 place-items-center rounded-full bg-gradient-to-br from-primary to-accent text-[0.6875rem] font-bold text-white shadow-[0_2px_6px_-2px_color-mix(in_srgb,var(--primary)_70%,transparent)] ring-2 ring-surface">
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
          <div className="absolute right-0 mt-2 w-72 overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface shadow-[var(--shadow-lg)]">
            <div className="flex items-center gap-3 border-b border-line bg-gradient-to-br from-primary-soft/55 to-transparent px-4 py-3.5">
              <span className="grid size-10 shrink-0 place-items-center rounded-full bg-gradient-to-br from-primary to-accent text-xs font-bold text-white shadow-[0_2px_6px_-2px_color-mix(in_srgb,var(--primary)_70%,transparent)] ring-2 ring-surface">
                {initials(viewer.displayName)}
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-foreground">
                  {viewer.displayName}
                </p>
                <p className="truncate text-xs text-muted">{viewer.email}</p>
                {corpId && (
                  <p className="mt-1 flex items-center gap-1 truncate text-[0.6875rem] font-bold tracking-[0.02em] text-primary-strong">
                    <ShieldCheck aria-hidden="true" className="size-3" />
                    <span className="sr-only">Rezumi Corp ID: </span>
                    {corpId}
                  </p>
                )}
              </div>
            </div>
            <div className="p-2">
              <p className="eyebrow px-3 pb-1 pt-1.5 !text-[0.625rem]">
                Manage
              </p>
              {workspaceUtilityNavigation.map(({ href, icon: Icon, label }) => (
                <Link
                  className="flex min-h-11 items-center gap-2.5 rounded-[var(--radius-control)] px-3 text-sm font-semibold text-foreground transition-colors hover:bg-surface-subtle"
                  href={href}
                  key={href}
                >
                  <Icon
                    aria-hidden="true"
                    className="size-4 text-muted-strong"
                  />
                  {label}
                </Link>
              ))}
              <div className="mt-1 border-t border-line pt-1">
                {accountActions}
              </div>
            </div>
          </div>
        </details>
      </div>
    </header>
  );
}
