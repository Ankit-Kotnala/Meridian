import {
  Activity,
  Archive,
  BarChart3,
  BookOpenCheck,
  BriefcaseBusiness,
  ChevronLeft,
  CircleUserRound,
  FileHeart,
  LayoutDashboard,
  Network,
  Settings,
  Target,
  type LucideIcon,
  WandSparkles,
} from "lucide-react";
import Link from "next/link";

import { cn } from "@careeros/ui";

import { CareerOsLogo } from "@/shared/components/career-os-logo";

const navigation: ReadonlyArray<{
  label: string;
  icon: LucideIcon;
  href: string;
  active?: boolean;
}> = [
  {
    label: "Dashboard",
    icon: LayoutDashboard,
    href: "#demo-overview",
    active: true,
  },
  { label: "Resume Health", icon: FileHeart, href: "#resume-health" },
  { label: "Career Profile", icon: CircleUserRound, href: "#evidence" },
  { label: "Evidence Vault", icon: Archive, href: "#evidence" },
  { label: "Role Explorer", icon: Target, href: "#role-readiness" },
  { label: "Job Match", icon: WandSparkles, href: "#role-readiness" },
  { label: "Applications", icon: BriefcaseBusiness, href: "#applications" },
  { label: "Interview Prep", icon: BookOpenCheck, href: "#applications" },
  { label: "Networking", icon: Network, href: "#applications" },
  { label: "Career Growth", icon: Activity, href: "#evidence" },
  { label: "Analytics", icon: BarChart3, href: "#applications" },
  { label: "Settings", icon: Settings, href: "#demo-overview" },
];

export function Sidebar({
  collapsed = false,
  onCollapse,
  onNavigate,
}: {
  collapsed?: boolean;
  onCollapse?: () => void;
  onNavigate?: () => void;
}) {
  return (
    <div className="flex h-full flex-col bg-navy text-white">
      <div
        className={cn(
          "flex h-17 items-center border-b border-white/10",
          collapsed ? "justify-center px-2" : "px-4",
        )}
      >
        <CareerOsLogo compact={collapsed} inverted />
      </div>
      <nav
        aria-label="Application navigation"
        className="flex-1 overflow-y-auto px-2 py-4"
      >
        <p
          className={cn(
            "mb-2 px-2 text-[0.6rem] font-extrabold uppercase tracking-[0.14em] text-slate-500",
            collapsed && "sr-only",
          )}
        >
          Workspace
        </p>
        <ul className="space-y-1">
          {navigation.map(({ label, icon: Icon, href, active }) => (
            <li key={label}>
              <Link
                {...(active ? { "aria-current": "page" as const } : {})}
                className={cn(
                  "flex min-h-10 items-center rounded-xl text-xs font-semibold transition",
                  collapsed ? "justify-center px-2" : "gap-3 px-3",
                  active
                    ? "bg-primary text-white shadow-[0_8px_24px_rgba(91,70,245,.2)]"
                    : "text-slate-300 hover:bg-white/8 hover:text-white",
                )}
                href={href}
                {...(onNavigate ? { onClick: onNavigate } : {})}
                {...(collapsed ? { title: label } : {})}
              >
                <Icon aria-hidden="true" className="size-4 shrink-0" />
                {!collapsed && <span>{label}</span>}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      <div className="border-t border-white/10 p-2">
        <div
          className={cn(
            "mb-2 rounded-xl bg-white/6 p-3",
            collapsed && "hidden",
          )}
        >
          <p className="text-[0.62rem] font-bold uppercase tracking-wider text-violet-300">
            Preview workspace
          </p>
          <p className="mt-1 text-[0.65rem] leading-4 text-slate-400">
            Fictional data only. Accounts arrive in Phase 1.
          </p>
        </div>
        {onCollapse && (
          <button
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="flex min-h-10 w-full items-center justify-center rounded-xl text-slate-400 transition hover:bg-white/8 hover:text-white"
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
        )}
      </div>
    </div>
  );
}
