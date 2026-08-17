import {
  Archive,
  BarChart3,
  BookOpenCheck,
  ClipboardList,
  FileDiff,
  FileHeart,
  FileText,
  LayoutDashboard,
  Network,
  NotebookPen,
  Settings,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  UserRound,
  UserRoundCheck,
  type LucideIcon,
} from "lucide-react";

export type WorkspaceNavigationItem = {
  href: string;
  icon: LucideIcon;
  label: string;
};

/**
 * One primary sidebar destination.
 *
 * `routes` lists every path prefix the section owns so the rail highlights
 * correctly from any nested route, and `tools` is the section's own
 * sub-navigation. A section with fewer than two tools renders no sub-navigation.
 * Consolidating here rather than deleting routes keeps every existing URL valid.
 */
export type WorkspaceSection = {
  href: string;
  icon: LucideIcon;
  id: string;
  label: string;
  routes: readonly string[];
  tools: readonly WorkspaceNavigationItem[];
};

export const workspaceSections: readonly WorkspaceSection[] = [
  {
    href: "/dashboard",
    icon: LayoutDashboard,
    id: "home",
    label: "Home",
    routes: ["/dashboard"],
    tools: [],
  },
  {
    href: "/career-profile",
    icon: UserRound,
    id: "career-record",
    label: "Career Record",
    routes: ["/career-profile", "/evidence", "/achievement-inbox"],
    tools: [
      { href: "/career-profile", icon: UserRound, label: "Profile" },
      { href: "/evidence", icon: Archive, label: "Evidence Vault" },
      {
        href: "/achievement-inbox",
        icon: NotebookPen,
        label: "Achievement Inbox",
      },
      {
        href: "/career-profile/imports",
        icon: FileDiff,
        label: "Resume Imports",
      },
    ],
  },
  {
    href: "/resume-health/account",
    icon: FileHeart,
    id: "resume-studio",
    label: "Resume Studio",
    routes: ["/resume-health", "/resume-builder", "/change-studio"],
    tools: [
      {
        href: "/resume-health/account",
        icon: FileHeart,
        label: "Resume Health",
      },
      { href: "/resume-builder", icon: FileText, label: "Builder" },
      { href: "/change-studio", icon: Sparkles, label: "Change Studio" },
    ],
  },
  {
    href: "/job-match",
    icon: Target,
    id: "opportunities",
    label: "Opportunities",
    routes: ["/job-match", "/role-explorer"],
    tools: [
      { href: "/job-match", icon: Target, label: "Job Match" },
      { href: "/role-explorer", icon: Target, label: "Role Explorer" },
    ],
  },
  {
    href: "/applications",
    icon: ClipboardList,
    id: "applications",
    label: "Applications",
    routes: ["/applications"],
    tools: [],
  },
  {
    href: "/interview-prep",
    icon: BookOpenCheck,
    id: "prepare",
    label: "Prepare",
    routes: ["/interview-prep", "/networking"],
    tools: [
      {
        href: "/interview-prep",
        icon: BookOpenCheck,
        label: "Interview Prep",
      },
      { href: "/networking", icon: Network, label: "Networking" },
    ],
  },
  {
    href: "/career-growth",
    icon: TrendingUp,
    id: "growth",
    label: "Growth",
    routes: ["/career-growth", "/analytics"],
    tools: [
      { href: "/career-growth", icon: TrendingUp, label: "Career Growth" },
      { href: "/analytics", icon: BarChart3, label: "Analytics" },
    ],
  },
];

export const workspaceUtilityNavigation: readonly WorkspaceNavigationItem[] = [
  { href: "/onboarding", icon: UserRoundCheck, label: "Setup Guide" },
  { href: "/settings", icon: Settings, label: "Settings" },
  { href: "/admin", icon: ShieldCheck, label: "Admin Console" },
];

export function isCurrentWorkspacePath(pathname: string, href: string) {
  if (href === "/dashboard") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

function ownsPath(pathname: string, route: string) {
  if (route === "/dashboard") return pathname === route;
  return pathname === route || pathname.startsWith(`${route}/`);
}

export function isCurrentWorkspaceSection(
  pathname: string,
  section: WorkspaceSection,
) {
  return section.routes.some((route) => ownsPath(pathname, route));
}

export function resolveWorkspaceSection(
  pathname: string,
): WorkspaceSection | undefined {
  return workspaceSections.find((section) =>
    isCurrentWorkspaceSection(pathname, section),
  );
}

/**
 * Resolve the most specific tool for a path so sub-navigation highlights the
 * deepest match. `/career-profile/imports` must win over `/career-profile`.
 */
export function resolveWorkspaceTool(
  pathname: string,
  section: WorkspaceSection,
): WorkspaceNavigationItem | undefined {
  return section.tools
    .filter(({ href }) => isCurrentWorkspacePath(pathname, href))
    .sort((left, right) => right.href.length - left.href.length)[0];
}

export function resolveWorkspaceContext(pathname: string) {
  const section = resolveWorkspaceSection(pathname);
  if (section) {
    const tool = resolveWorkspaceTool(pathname, section);
    return {
      group: section.label,
      label: tool?.label ?? section.label,
    };
  }
  const utility = workspaceUtilityNavigation.find(({ href }) =>
    isCurrentWorkspacePath(pathname, href),
  );
  return utility
    ? { group: "Account", label: utility.label }
    : { group: "Workspace", label: "Rezumi" };
}
