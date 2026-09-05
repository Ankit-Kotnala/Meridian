"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  workspaceSectionNavItemClassName,
  workspaceSectionNavListClassName,
} from "@/shared/workspace/section-nav-styles";
import { useInterviewPrepWorkspaceMetrics } from "@/shared/workspace/interview-prep-workspace-metrics";

import {
  resolveWorkspaceSection,
  resolveWorkspaceSectionTools,
  resolveWorkspaceTool,
} from "./workspace-navigation";

function labelForTool(
  href: string,
  label: string,
  practiceLabCount: number | undefined,
) {
  if (href === "/interview-prep/practice-lab" && practiceLabCount !== undefined) {
    return `Practice lab (${practiceLabCount})`;
  }
  return label;
}

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
  const metrics = useInterviewPrepWorkspaceMetrics();
  const hideStudioSubNav =
    pathname === "/resume-health/account" ||
    pathname.startsWith("/resume-health/account/report/") ||
    pathname.startsWith("/resume-health/account/review/") ||
    pathname.startsWith("/resume-health/account/processing/");
  if (hideStudioSubNav) return null;

  const section = resolveWorkspaceSection(pathname);
  if (!section) return null;

  const tools = resolveWorkspaceSectionTools(pathname, section);
  if (tools.length < 2) return null;

  const current = resolveWorkspaceTool(pathname, section);
  const practiceLabCount = metrics?.practiceLabCount;

  return (
    <div className="border-b border-line bg-surface">
      <nav
        aria-label={`${section.label} sections`}
        className={workspaceSectionNavListClassName()}
      >
        {tools.map(({ href, label }) => {
          const active = current?.href === href;
          return (
            <Link
              {...(active ? { "aria-current": "page" as const } : {})}
              className={workspaceSectionNavItemClassName(active)}
              href={href}
              key={href}
            >
              {labelForTool(href, label, practiceLabCount)}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
