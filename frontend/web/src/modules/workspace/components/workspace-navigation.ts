import {
  Archive,
  BarChart3,
  BookOpenCheck,
  Briefcase,
  Calendar,
  FileDiff,
  FileText,
  Home,
  Network,
  NotebookPen,
  Search,
  Settings,
  ShieldCheck,
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
  /** One-line orientation shown under the section name in the top bar. */
  subtitle: string;
  tools: readonly WorkspaceNavigationItem[];
};

export const workspaceSections: readonly WorkspaceSection[] = [
  {
    href: "/dashboard",
    icon: Home,
    id: "home",
    label: "Home",
    subtitle: "Your career workspace",
    routes: ["/dashboard"],
    tools: [],
  },
  {
    href: "/career-profile",
    icon: UserRound,
    id: "career-record",
    label: "Profile",
    subtitle: "Your career source of truth",
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
    icon: FileText,
    id: "resume-studio",
    label: "Resumes",
    subtitle: "Drafts, health, and exports",
    routes: ["/resume-health", "/resume-builder", "/change-studio"],
    tools: [],
  },
  {
    href: "/job-match",
    icon: Search,
    id: "opportunities",
    label: "Job search",
    subtitle: "Find and match open roles",
    routes: ["/job-match", "/role-explorer"],
    tools: [
      { href: "/job-match", icon: Search, label: "Job search" },
      {
        href: "/job-match/saved",
        icon: Briefcase,
        label: "Saved jobs",
      },
      {
        href: "/job-match/roles",
        icon: UserRoundCheck,
        label: "Role matching",
      },
    ],
  },
  {
    href: "/applications",
    icon: Briefcase,
    id: "applications",
    label: "Applications",
    subtitle: "Track every application",
    routes: ["/applications"],
    tools: [],
  },
  {
    href: "/interview-prep",
    icon: Calendar,
    id: "prepare",
    label: "Interview prep",
    subtitle: "Practice and outreach",
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
    subtitle: "Plan your next step",
    routes: ["/career-growth", "/analytics"],
    tools: [
      { href: "/career-growth", icon: TrendingUp, label: "Growth" },
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
  if (href === "/interview-prep") {
    if (
      pathname === "/interview-prep/practice-lab" ||
      pathname.startsWith("/interview-prep/practice-lab/")
    ) {
      return false;
    }
    return pathname === href || pathname.startsWith(`${href}/`);
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function isInterviewPrepWorkspacePath(pathname: string) {
  return (
    pathname === "/interview-prep" ||
    pathname === "/interview-prep/practice-lab"
  );
}

export const interviewPrepWorkspaceTools: readonly WorkspaceNavigationItem[] = [
  {
    href: "/interview-prep",
    icon: BookOpenCheck,
    label: "Skill journey",
  },
  {
    href: "/interview-prep/practice-lab",
    icon: BookOpenCheck,
    label: "Practice lab",
  },
];

export function resolveWorkspaceSectionTools(
  pathname: string,
  section: WorkspaceSection,
): readonly WorkspaceNavigationItem[] {
  if (section.id === "prepare" && isInterviewPrepWorkspacePath(pathname)) {
    return interviewPrepWorkspaceTools;
  }
  return section.tools;
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
  return resolveWorkspaceSectionTools(pathname, section)
    .filter(({ href }) => isCurrentWorkspacePath(pathname, href))
    .sort((left, right) => right.href.length - left.href.length)[0];
}

export function resolveWorkspaceContext(pathname: string) {
  const section = resolveWorkspaceSection(pathname);
  if (section) {
    const tool = resolveWorkspaceTool(pathname, section);
    return {
      group: section.label,
      icon: section.icon,
      label: tool?.label ?? section.label,
      subtitle: section.subtitle,
    };
  }
  const utility = workspaceUtilityNavigation.find(({ href }) =>
    isCurrentWorkspacePath(pathname, href),
  );
  return utility
    ? {
        group: "Account",
        icon: utility.icon,
        label: utility.label,
        subtitle: "Manage your account",
      }
    : {
        group: "Workspace",
        icon: Home,
        label: "Meridian",
        subtitle: "Your career workspace",
      };
}
