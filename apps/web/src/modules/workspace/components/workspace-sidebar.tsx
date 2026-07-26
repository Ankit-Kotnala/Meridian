import {
  Activity,
  Archive,
  BarChart3,
  BookOpenCheck,
  BriefcaseBusiness,
  ChevronLeft,
  ClipboardList,
  FileText,
  FileHeart,
  LayoutDashboard,
  Network,
  Settings,
  Sparkles,
  Target,
  UserRoundCheck,
  UserRound,
  X,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@careeros/ui";

import { CareerOsLogo } from "@/shared/components/career-os-logo";

const availableNavigation: ReadonlyArray<{
  href: string;
  icon: LucideIcon;
  label: string;
}> = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/resume-health/account", icon: FileHeart, label: "Resume Health" },
  { href: "/career-profile", icon: UserRound, label: "Career Profile" },
  { href: "/evidence", icon: Archive, label: "Evidence Vault" },
  { href: "/role-explorer", icon: Target, label: "Role Explorer" },
  { href: "/job-match", icon: BriefcaseBusiness, label: "Job Match" },
  { href: "/applications", icon: ClipboardList, label: "Applications" },
  { href: "/interview-prep", icon: BookOpenCheck, label: "Interview Prep" },
  { href: "/networking", icon: Network, label: "Networking" },
  { href: "/career-growth", icon: Activity, label: "Career Growth" },
  { href: "/analytics", icon: BarChart3, label: "Analytics" },
  { href: "/change-studio", icon: Sparkles, label: "Change Studio" },
  { href: "/resume-builder", icon: FileText, label: "Resume Builder" },
  { href: "/onboarding", icon: UserRoundCheck, label: "Onboarding" },
  { href: "/settings", icon: Settings, label: "Settings" },
];

function isCurrent(pathname: string, href: string): boolean {
  if (href === "/dashboard") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
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
          "flex h-17 items-center border-b border-white/10",
          collapsed ? "justify-center px-2" : "justify-between px-4",
        )}
      >
        <CareerOsLogo compact={collapsed} href="/dashboard" inverted />
        {onClose && (
          <button
            aria-label="Close application navigation"
            className="grid size-10 place-items-center rounded-xl text-slate-300 hover:bg-white/10 hover:text-white"
            onClick={onClose}
            type="button"
          >
            <X aria-hidden="true" className="size-5" />
          </button>
        )}
      </div>

      <nav
        aria-label="Application navigation"
        className="flex-1 overflow-y-auto px-2 py-4"
      >
        <p
          className={cn(
            "mb-2 px-2 text-[0.65rem] font-extrabold uppercase tracking-[0.14em] text-slate-400",
            collapsed && "sr-only",
          )}
        >
          Workspace
        </p>
        <ul className="space-y-1">
          {availableNavigation.map(({ label, icon: Icon, href }) => {
            const active = isCurrent(pathname, href);
            return (
              <li key={href}>
                <Link
                  {...(active ? { "aria-current": "page" as const } : {})}
                  {...(collapsed ? { "aria-label": label, title: label } : {})}
                  className={cn(
                    "flex min-h-11 items-center rounded-xl text-xs font-semibold transition",
                    collapsed ? "justify-center px-2" : "gap-3 px-3",
                    active
                      ? "bg-primary text-white shadow-[0_8px_24px_rgba(91,70,245,.2)]"
                      : "text-slate-200 hover:bg-white/8 hover:text-white",
                  )}
                  href={href}
                  {...(onNavigate ? { onClick: onNavigate } : {})}
                >
                  <Icon aria-hidden="true" className="size-4 shrink-0" />
                  {!collapsed && <span>{label}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {onCollapse && (
        <div className="border-t border-white/10 p-2">
          <button
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="flex min-h-11 w-full items-center justify-center rounded-xl text-slate-300 transition hover:bg-white/8 hover:text-white"
            onClick={onCollapse}
            type="button"
          >
            <ChevronLeft
              aria-hidden="true"
              className={cn("size-4 transition", collapsed && "rotate-180")}
            />
            {!collapsed && (
              <span className="ml-2 text-xs font-semibold">
                Collapse sidebar
              </span>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
