"use client";

import { PanelLeftClose, X } from "lucide-react";
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
        "group relative flex min-h-10 items-center rounded-[var(--radius-control)] text-[0.8125rem] font-semibold transition-[background-color,color,transform] duration-150",
        collapsed ? "justify-center px-2" : "gap-3 px-3",
        active
          ? "bg-gradient-to-r from-white/[0.14] via-white/[0.06] to-transparent text-white shadow-[inset_0_0_0_1px_rgba(255,255,255,0.07)] before:absolute before:inset-y-1.5 before:left-0 before:w-[3px] before:rounded-full before:bg-gradient-to-b before:from-accent before:to-primary before:shadow-[0_0_12px_color-mix(in_srgb,var(--accent)_65%,transparent)]"
          : "text-emerald-50/72 hover:translate-x-0.5 hover:bg-white/7 hover:text-white",
      )}
      href={href}
      {...(onNavigate ? { onClick: onNavigate } : {})}
    >
      <span
        className={cn(
          "grid size-7 shrink-0 place-items-center rounded-md transition-colors",
          active
            ? "bg-gradient-to-br from-accent/30 to-primary/25 text-accent-soft ring-1 ring-white/10"
            : "text-emerald-50/70 group-hover:bg-white/8 group-hover:text-white",
        )}
      >
        <Icon aria-hidden="true" className="size-4" strokeWidth={2} />
      </span>
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
    <div className="relative flex h-full flex-col overflow-hidden bg-navy bg-[linear-gradient(180deg,color-mix(in_srgb,var(--navy-hover)_55%,transparent),transparent_45%)] text-white before:pointer-events-none before:absolute before:inset-x-0 before:top-0 before:h-72 before:bg-[radial-gradient(120%_60%_at_50%_0%,rgba(55,171,144,0.2),transparent_72%)] after:pointer-events-none after:absolute after:inset-y-0 after:right-0 after:w-px after:bg-gradient-to-b after:from-white/12 after:via-white/5 after:to-transparent">
      <div
        className={cn(
          "relative flex min-h-16 border-b border-white/10",
          collapsed
            ? "flex-col items-center gap-2 px-2 py-3"
            : "items-center justify-between px-4",
        )}
      >
        <RezumiLogo compact={collapsed} href="/dashboard" inverted />
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
        {onCollapse && (
          <button
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="grid size-8 shrink-0 place-items-center rounded-lg text-emerald-50/60 transition-colors hover:bg-white/10 hover:text-white"
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
        className="relative flex-1 overflow-y-auto px-2 py-3"
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
        <div className="h-2" />
      </nav>

      {/* Soft scroll fade so long navigation lists dissolve into the rail. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 bottom-0 h-12 bg-gradient-to-t from-navy via-navy/70 to-transparent"
      />
    </div>
  );
}
