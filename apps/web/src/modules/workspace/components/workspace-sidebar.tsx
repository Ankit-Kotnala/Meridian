"use client";

import { ChevronLeft, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@careeros/ui";

import { CareerOsLogo } from "@/shared/components/career-os-logo";

import {
  isCurrentWorkspacePath,
  workspaceNavigationGroups,
  workspaceUtilityNavigation,
  type WorkspaceNavigationItem,
} from "./workspace-navigation";

function NavigationLink({
  collapsed,
  item: { href, icon: Icon, label },
  onNavigate,
  pathname,
}: {
  collapsed: boolean;
  item: WorkspaceNavigationItem;
  onNavigate?: (() => void) | undefined;
  pathname: string;
}) {
  const active = isCurrentWorkspacePath(pathname, href);
  return (
    <Link
      {...(active ? { "aria-current": "page" as const } : {})}
      {...(collapsed ? { "aria-label": label, title: label } : {})}
      className={cn(
        "group relative flex min-h-10 items-center rounded-[var(--radius-control)] text-[0.8125rem] font-semibold transition-colors",
        collapsed ? "justify-center px-2" : "gap-3 px-3",
        active
          ? "bg-white/12 text-white before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:rounded-full before:bg-white"
          : "text-emerald-50/75 hover:bg-white/7 hover:text-white",
      )}
      href={href}
      {...(onNavigate ? { onClick: onNavigate } : {})}
    >
      <Icon aria-hidden="true" className="size-4 shrink-0" strokeWidth={2} />
      {!collapsed && <span>{label}</span>}
    </Link>
  );
}

export function WorkspaceSidebar({
  collapsed = false,
  onClose,
  onCollapse,
  onNavigate,
}: {
  collapsed?: boolean;
  onClose?: () => void;
  onCollapse?: () => void;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col bg-navy text-white">
      <div
        className={cn(
          "flex min-h-16 items-center border-b border-white/10",
          collapsed ? "justify-center px-2" : "justify-between px-4",
        )}
      >
        <CareerOsLogo compact={collapsed} href="/dashboard" inverted />
        {onClose && (
          <button
            aria-label="Close application navigation"
            className="grid size-10 place-items-center rounded-[var(--radius-control)] text-emerald-50/75 hover:bg-white/10 hover:text-white"
            onClick={onClose}
            type="button"
          >
            <X aria-hidden="true" className="size-5" />
          </button>
        )}
      </div>

      <nav
        aria-label="Application navigation"
        className="flex-1 overflow-y-auto px-2 py-3"
      >
        {workspaceNavigationGroups.map((group, groupIndex) => (
          <section
            aria-labelledby={`workspace-nav-${groupIndex}`}
            className={cn(groupIndex > 0 && "mt-4")}
            key={group.label}
          >
            <h2
              className={cn(
                "mb-1.5 px-3 text-[0.625rem] font-bold uppercase tracking-[0.13em] text-emerald-100/50",
                collapsed && "sr-only",
              )}
              id={`workspace-nav-${groupIndex}`}
            >
              {group.label}
            </h2>
            <ul className="space-y-0.5">
              {group.items.map((item) => (
                <li key={item.href}>
                  <NavigationLink
                    collapsed={collapsed}
                    item={item}
                    onNavigate={onNavigate}
                    pathname={pathname}
                  />
                </li>
              ))}
            </ul>
          </section>
        ))}
      </nav>

      <div className="border-t border-white/10 p-2">
        <ul className="space-y-0.5">
          {workspaceUtilityNavigation.map((item) => (
            <li key={item.href}>
              <NavigationLink
                collapsed={collapsed}
                item={item}
                onNavigate={onNavigate}
                pathname={pathname}
              />
            </li>
          ))}
        </ul>
        {onCollapse && (
          <button
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={cn(
              "mt-1 flex min-h-10 w-full items-center rounded-[var(--radius-control)] text-emerald-50/70 transition-colors hover:bg-white/7 hover:text-white",
              collapsed ? "justify-center" : "justify-start px-3",
            )}
            onClick={onCollapse}
            type="button"
          >
            <ChevronLeft
              aria-hidden="true"
              className={cn("size-4 transition", collapsed && "rotate-180")}
            />
            {!collapsed && (
              <span className="ml-3 text-xs font-semibold">Collapse</span>
            )}
          </button>
        )}
      </div>
    </div>
  );
}
