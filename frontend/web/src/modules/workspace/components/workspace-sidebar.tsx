"use client";

import { ChevronLeft, ChevronRight, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@rezumi/ui";

import { RezumiLogo } from "@/shared/components/rezumi-logo";

import {
  isCurrentWorkspaceSection,
  workspaceSections,
  type WorkspaceSection,
} from "./workspace-navigation";

/**
 * Applied inline because `globals.css` sets `* { border-color: var(--border) }`
 * outside any cascade layer, which beats layered `border-white/12` utilities
 * and would paint these rules in the light-theme border colour on navy.
 */
const railRule = "rgb(255 255 255 / 0.12)";

function NavigationLink({
  collapsed,
  onNavigate,
  pathname,
  section,
}: {
  collapsed: boolean;
  onNavigate?: (() => void) | undefined;
  pathname: string;
  section: WorkspaceSection;
}) {
  const { href, icon: Icon, label } = section;
  const active = isCurrentWorkspaceSection(pathname, section);
  return (
    <Link
      {...(active ? { "aria-current": "page" as const } : {})}
      {...(collapsed ? { "aria-label": label, title: label } : {})}
      className={cn(
        "flex min-h-9 items-center rounded-[var(--radius-small)] text-[0.8125rem] transition-colors duration-200",
        collapsed ? "justify-center px-2" : "gap-3 px-3",
        active
          ? "bg-white/[0.09] font-semibold text-white"
          : "font-medium text-white/65 hover:bg-white/[0.06] hover:text-white",
      )}
      href={href}
      {...(onNavigate ? { onClick: onNavigate } : {})}
    >
      <Icon aria-hidden="true" className="size-4 shrink-0" strokeWidth={1.6} />
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
          "flex min-h-[var(--topbar-height)] items-center border-b",
          collapsed ? "justify-center px-2 py-3" : "justify-between px-4",
        )}
        style={{ borderBottomColor: railRule }}
      >
        {collapsed ? (
          <RezumiLogo compact href="/dashboard" inverted />
        ) : (
          <Link
            aria-label="Meridian home"
            className="font-display text-[0.875rem] font-bold uppercase tracking-[0.16em] text-white"
            href="/dashboard"
          >
            Meridian
          </Link>
        )}
        {onClose && (
          <button
            aria-label="Close application navigation"
            className="grid size-10 place-items-center rounded-[var(--radius-control)] text-white/75 hover:bg-white/10 hover:text-white"
            onClick={onClose}
            type="button"
          >
            <X aria-hidden="true" className="size-5" />
          </button>
        )}
      </div>

      <nav
        aria-label="Application navigation"
        className="flex-1 overflow-y-auto px-2.5 py-3"
      >
        <ul className="space-y-0.5">
          {workspaceSections.map((section) => (
            <li key={section.id}>
              <NavigationLink
                collapsed={collapsed}
                onNavigate={onNavigate}
                pathname={pathname}
                section={section}
              />
            </li>
          ))}
        </ul>
      </nav>

      {onCollapse && (
        <div
          className="border-t px-2.5 py-3"
          style={{ borderTopColor: railRule }}
        >
          <button
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={cn(
              "flex min-h-9 w-full items-center rounded-[var(--radius-small)] text-[0.8125rem] font-medium text-white/55 transition-colors duration-200 hover:bg-white/[0.06] hover:text-white",
              collapsed ? "justify-center px-2" : "gap-3 px-3",
            )}
            onClick={onCollapse}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            type="button"
          >
            {collapsed ? (
              <ChevronRight aria-hidden="true" className="size-4 shrink-0" />
            ) : (
              <>
                <ChevronLeft aria-hidden="true" className="size-4 shrink-0" />
                <span>Collapse</span>
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
