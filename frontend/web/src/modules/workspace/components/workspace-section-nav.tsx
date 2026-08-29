"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@rezumi/ui";

import {
  resolveWorkspaceSection,
  resolveWorkspaceTool,
} from "./workspace-navigation";

/**
 * Sub-navigation for the tools inside the current section.
 *
 * This is what lets the sidebar stay at seven destinations: the sibling tools a
 * section owns move in here. It renders nothing for single-tool sections, and
 * sits outside `<main>` because it is navigation, not page content.
 */
export function WorkspaceSectionNav() {
  const pathname = usePathname();
  const hideStudioSubNav =
    pathname === "/resume-health/account" ||
    pathname.startsWith("/resume-health/account/report/") ||
    pathname.startsWith("/resume-health/account/review/") ||
    pathname.startsWith("/resume-health/account/processing/");
  if (hideStudioSubNav) return null;

  const section = resolveWorkspaceSection(pathname);
  if (!section || section.tools.length < 2) return null;
  const current = resolveWorkspaceTool(pathname, section);

  return (
    <div className="border-b border-line/80 bg-surface/45 backdrop-blur-sm">
      <nav
        aria-label={`${section.label} sections`}
        className="mx-auto flex w-full max-w-[var(--content-wide)] gap-1 overflow-x-auto px-[var(--space-page-inline)] py-2"
      >
        {section.tools.map(({ href, icon: Icon, label }) => {
          const active = current?.href === href;
          return (
            <Link
              {...(active ? { "aria-current": "page" as const } : {})}
              className={cn(
                "flex min-h-9 shrink-0 items-center gap-2 rounded-[var(--radius-control)] px-3 text-[0.8125rem] font-semibold transition-colors",
                active
                  ? "bg-primary-soft text-primary-strong shadow-[inset_0_0_0_1px_color-mix(in_srgb,var(--primary)_22%,transparent)]"
                  : "text-muted hover:bg-surface-subtle hover:text-foreground",
              )}
              href={href}
              key={href}
            >
              <Icon aria-hidden="true" className="size-4" />
              {label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
