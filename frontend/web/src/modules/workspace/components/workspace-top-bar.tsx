"use client";

import {
  Bell,
  ChevronDown,
  CircleQuestionMark,
  Menu,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";

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

function AccountMenu({
  accountActions,
  corpId,
  viewer,
}: {
  accountActions: ReactNode;
  corpId: string | null;
  viewer: WorkspaceViewer;
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(event: PointerEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
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

  return (
    <div className="relative shrink-0" ref={containerRef}>
      <button
        aria-controls={menuId}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={`Account menu for ${viewer.displayName}`}
        className="flex min-h-10 items-center gap-2 rounded-[var(--radius-pill)] border border-transparent px-1.5 text-left transition-colors hover:border-line hover:bg-surface-subtle"
        onClick={() => setOpen((value) => !value)}
        ref={triggerRef}
        type="button"
      >
        <span className="grid size-9 place-items-center rounded-full bg-primary text-xs font-bold text-white">
          {initials(viewer.displayName)}
        </span>
        <span className="hidden max-w-36 truncate text-sm font-semibold text-foreground md:block">
          {viewer.displayName}
        </span>
        <ChevronDown
          aria-hidden="true"
          className={`hidden size-3.5 text-muted transition-transform md:block ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div
          className="absolute right-0 z-50 mt-2 w-72 max-w-[calc(100vw-1rem)] overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface shadow-[var(--shadow-lg)]"
          id={menuId}
          role="menu"
        >
          <div className="flex items-center gap-3 border-b border-line px-4 py-3.5">
            <span className="grid size-10 shrink-0 place-items-center rounded-full bg-primary text-xs font-bold text-white">
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
                  <span className="sr-only">Meridian Corp ID: </span>
                  {corpId}
                </p>
              )}
            </div>
          </div>
          <div className="p-2">
            <p className="eyebrow px-3 pb-1 pt-1.5 !text-[0.625rem]">Manage</p>
            {workspaceUtilityNavigation.map(({ href, icon: Icon, label }) => (
              <Link
                className="flex min-h-10 items-center gap-2.5 rounded-[var(--radius-control)] px-3 text-sm font-semibold text-foreground transition-colors hover:bg-surface-subtle"
                href={href}
                key={href}
                onClick={() => setOpen(false)}
                role="menuitem"
              >
                <Icon aria-hidden="true" className="size-4 text-muted-strong" />
                {label}
              </Link>
            ))}
            <div className="mt-1 border-t border-line pt-1">
              {accountActions}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function WorkspaceTopBar({
  accountActions,
  hasUnreadNotifications = false,
  menuButtonRef,
  onOpenMenu,
  viewer,
}: {
  accountActions: ReactNode;
  /**
   * Drives the bell's unread dot. There is no notification feed yet, so this
   * stays false rather than showing an alert the account cannot act on.
   */
  hasUnreadNotifications?: boolean;
  menuButtonRef: RefObject<HTMLButtonElement | null>;
  onOpenMenu: () => void;
  viewer: WorkspaceViewer;
}) {
  const pathname = usePathname();
  const context = resolveWorkspaceContext(pathname);
  const ContextIcon = context.icon;
  const corpId = corpIdFor(viewer.id);

  return (
    <header className="sticky top-0 z-30 flex min-h-[var(--topbar-height)] items-center gap-2 border-b border-line bg-surface/95 px-3 backdrop-blur-sm sm:gap-4 sm:px-6">
      <button
        aria-label="Open application navigation"
        className="grid size-10 shrink-0 place-items-center rounded-[var(--radius-control)] border border-line text-foreground xl:hidden"
        onClick={onOpenMenu}
        ref={menuButtonRef}
        type="button"
      >
        <Menu aria-hidden="true" className="size-5" />
      </button>

      <div className="flex min-w-0 flex-1 items-center gap-3">
        <span
          aria-hidden="true"
          className="hidden size-9 shrink-0 place-items-center rounded-[var(--radius-control)] text-foreground sm:grid"
        >
          <ContextIcon className="size-5" strokeWidth={1.75} />
        </span>
        <div className="min-w-0 leading-tight">
          <p className="truncate text-[0.9375rem] font-bold text-foreground">
            {context.label}
          </p>
          <p className="truncate text-xs text-muted">{context.subtitle}</p>
        </div>
      </div>

      <div className="ml-auto flex shrink-0 items-center gap-1">
        <Link
          aria-label="Help and onboarding"
          className="grid size-10 place-items-center rounded-[var(--radius-control)] text-[0.8125rem] font-semibold text-muted-strong transition-colors hover:bg-surface-subtle hover:text-foreground sm:flex sm:w-auto sm:gap-1.5 sm:px-2.5"
          href="/onboarding"
        >
          <CircleQuestionMark aria-hidden="true" className="size-[1.125rem]" />
          <span className="hidden sm:inline">Help</span>
        </Link>

        <span aria-hidden="true" className="mx-1 h-6 w-px bg-line sm:mx-1.5" />

        <ThemeToggle />

        <Link
          aria-label={
            hasUnreadNotifications
              ? "Notification settings, unread notifications"
              : "Notification settings"
          }
          className="relative grid size-10 place-items-center rounded-[var(--radius-control)] text-muted-strong transition-colors hover:bg-surface-subtle hover:text-foreground"
          href="/settings/notifications"
          title="Notification settings"
        >
          <Bell aria-hidden="true" className="size-[1.125rem]" />
          {hasUnreadNotifications && (
            <span
              aria-hidden="true"
              className="absolute right-2 top-2 size-2 rounded-full bg-danger ring-2 ring-surface"
            />
          )}
        </Link>

        <AccountMenu
          accountActions={accountActions}
          corpId={corpId}
          viewer={viewer}
        />
      </div>
    </header>
  );
}
