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
 *
 * `scroll-strip` keeps it horizontally scrollable without painting a scrollbar
 * beside the last tab - see the rule in globals.css for why that is needed.
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
    <div className="border-b border-line bg-surface">
      <nav
        aria-label={`${section.label} sections`}
        className="mx-auto flex w-full max-w-[var(--content-wide)] gap-6 overflow-x-auto px-[var(--space-page-inline)] scroll-strip"
      >
        {section.tools.map(({ href, label }) => {
          const active = current?.href === href;
          return (
            <Link
              {...(active ? { "aria-current": "page" as const } : {})}
              className={cn(
                "-mb-px flex min-h-11 shrink-0 items-center border-b-2 text-[0.8125rem] font-semibold transition-colors",
                active
                  ? "border-info text-info"
                  : "border-transparent text-foreground hover:border-line-strong hover:text-muted-strong",
              )}
              href={href}
              key={href}
            >
              {label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
