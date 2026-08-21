"use client";

import { PanelLeftClose, Rocket, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@rezumi/ui";

import { RezumiLogo } from "@/shared/components/rezumi-logo";

import {
  isCurrentWorkspaceSection,
  workspaceSections,
  type WorkspaceSection,
} from "./workspace-navigation";

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
        "flex min-h-10 items-center rounded-[var(--radius-control)] text-[0.8125rem] font-semibold transition-colors duration-150",
        collapsed ? "justify-center px-2" : "gap-3 px-3",
        active
          ? "bg-[#e6f4ea] text-[#0b3d2e]"
          : "text-white/75 hover:bg-white/10 hover:text-white",
      )}
      href={href}
      {...(onNavigate ? { onClick: onNavigate } : {})}
    >
      <Icon aria-hidden="true" className="size-[1.125rem] shrink-0" strokeWidth={1.75} />
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
          "flex min-h-16 border-b border-white/10",
          collapsed
            ? "flex-col items-center gap-2 px-2 py-3"
            : "items-center justify-between px-4",
        )}
      >
        <RezumiLogo compact={collapsed} href="/dashboard" inverted />
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
        {onCollapse && (
          <button
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="grid size-8 shrink-0 place-items-center rounded-lg text-white/60 transition-colors hover:bg-white/10 hover:text-white"
            onClick={onCollapse}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            type="button"
          >
            <PanelLeftClose
              aria-hidden="true"
              className={cn(
                "size-[1.15rem] transition",
                collapsed && "rotate-180",
              )}
            />
          </button>
        )}
      </div>

      <nav
        aria-label="Application navigation"
        className="flex-1 overflow-y-auto px-3 py-4"
      >
        <ul className="space-y-1">
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

      {!collapsed && (
        <div className="px-3 pb-4">
          <div className="workspace-promo px-4 py-4">
            <Rocket
              aria-hidden="true"
              className="size-5 text-accent-soft"
            />
            <p className="mt-2 text-sm font-bold leading-snug text-white">
              Better resumes,
              <br />
              Bigger opportunities.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
