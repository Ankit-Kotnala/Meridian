import { Menu, UserRound } from "lucide-react";
import Link from "next/link";
import type { ReactNode, RefObject } from "react";

import type { WorkspaceViewer } from "./workspace-shell";

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
  return (
    <header className="sticky top-0 z-30 flex min-h-17 items-center justify-between gap-4 border-b border-line bg-white/95 px-4 backdrop-blur-lg sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <button
          aria-label="Open application navigation"
          className="grid size-11 shrink-0 place-items-center rounded-xl border border-line bg-white text-foreground lg:hidden"
          onClick={onOpenMenu}
          ref={menuButtonRef}
          type="button"
        >
          <Menu aria-hidden="true" className="size-5" />
        </button>
        <div className="min-w-0">
          <p className="truncate text-xs font-extrabold uppercase tracking-[0.08em] text-primary">
            Protected workspace
          </p>
          <p className="mt-0.5 hidden text-xs text-muted sm:block">
            Signed in as {viewer.email}
          </p>
        </div>
      </div>

      <details className="group relative">
        <summary className="flex min-h-11 list-none items-center gap-2 rounded-xl px-1.5 text-left hover:bg-slate-100 [&::-webkit-details-marker]:hidden">
          <span className="grid size-9 place-items-center rounded-full bg-[linear-gradient(135deg,#5b46f5,#9d7bff)] text-xs font-black text-white shadow-sm">
            {initials(viewer.displayName)}
          </span>
          <span className="hidden min-w-0 leading-tight sm:block">
            <span className="block max-w-40 truncate text-xs font-extrabold text-foreground">
              {viewer.displayName}
            </span>
            <span className="mt-0.5 block text-[0.65rem] text-muted">
              Account menu
            </span>
          </span>
        </summary>
        <div className="absolute right-0 mt-2 w-64 rounded-2xl border border-line bg-white p-2 shadow-lg">
          <div className="border-b border-line px-3 py-2.5">
            <p className="truncate text-sm font-extrabold text-foreground">
              {viewer.displayName}
            </p>
            <p className="mt-1 truncate text-xs text-muted">{viewer.email}</p>
          </div>
          <Link
            className="mt-1 flex min-h-11 items-center gap-2 rounded-xl px-3 text-sm font-bold text-foreground hover:bg-slate-100"
            href="/settings"
          >
            <UserRound aria-hidden="true" className="size-4" /> Account settings
          </Link>
          <div className="mt-1 border-t border-line pt-1">{accountActions}</div>
        </div>
      </details>
    </header>
  );
}
