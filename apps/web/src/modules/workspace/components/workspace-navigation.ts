import {
  Activity,
  Archive,
  BarChart3,
  BookOpenCheck,
  BriefcaseBusiness,
  ClipboardList,
  FileHeart,
  FileText,
  LayoutDashboard,
  Network,
  NotebookPen,
  Settings,
  Target,
  UserRound,
  UserRoundCheck,
  type LucideIcon,
} from "lucide-react";

export type WorkspaceNavigationItem = {
  href: string;
  icon: LucideIcon;
  label: string;
};

export type WorkspaceNavigationGroup = {
  items: readonly WorkspaceNavigationItem[];
  label: string;
};

export const workspaceNavigationGroups: readonly WorkspaceNavigationGroup[] = [
  {
    label: "Overview",
    items: [{ href: "/dashboard", icon: LayoutDashboard, label: "Home" }],
  },
  {
    label: "Career record",
    items: [
      { href: "/career-profile", icon: UserRound, label: "Career Profile" },
      { href: "/evidence", icon: Archive, label: "Evidence Vault" },
      {
        href: "/achievement-inbox",
        icon: NotebookPen,
        label: "Achievement Inbox",
      },
    ],
  },
  {
    label: "Opportunities",
    items: [
      { href: "/role-explorer", icon: Target, label: "Role Explorer" },
      { href: "/job-match", icon: BriefcaseBusiness, label: "Job Match" },
      { href: "/applications", icon: ClipboardList, label: "Applications" },
    ],
  },
  {
    label: "Create and prepare",
    items: [
      {
        href: "/resume-health/account",
        icon: FileHeart,
        label: "Resume Health",
      },
      { href: "/resume-builder", icon: FileText, label: "Resume Builder" },
      { href: "/change-studio", icon: NotebookPen, label: "Change Studio" },
      {
        href: "/interview-prep",
        icon: BookOpenCheck,
        label: "Interview Prep",
      },
      { href: "/networking", icon: Network, label: "Networking" },
    ],
  },
  {
    label: "Long-term growth",
    items: [
      { href: "/career-growth", icon: Activity, label: "Career Growth" },
      { href: "/analytics", icon: BarChart3, label: "Analytics" },
    ],
  },
];

export const workspaceUtilityNavigation: readonly WorkspaceNavigationItem[] = [
  { href: "/onboarding", icon: UserRoundCheck, label: "Setup Guide" },
  { href: "/settings", icon: Settings, label: "Settings" },
];

export function isCurrentWorkspacePath(pathname: string, href: string) {
  if (href === "/dashboard") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function resolveWorkspaceContext(pathname: string) {
  for (const group of workspaceNavigationGroups) {
    const item = group.items.find(({ href }) =>
      isCurrentWorkspacePath(pathname, href),
    );
    if (item) return { group: group.label, label: item.label };
  }
  const utility = workspaceUtilityNavigation.find(({ href }) =>
    isCurrentWorkspacePath(pathname, href),
  );
  return utility
    ? { group: "Account", label: utility.label }
    : { group: "Workspace", label: "CareerOS" };
}
