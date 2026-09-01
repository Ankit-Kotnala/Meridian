"use client";

import {
  BellRing,
  ClipboardList,
  CreditCard,
  KeyRound,
  Laptop,
  Link2,
  ShieldCheck,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@rezumi/ui";

import { useSettingsCapabilities } from "./settings-capabilities-context";

type SettingsNavItem = {
  href: string;
  icon: LucideIcon;
  label: string;
  visible?: (capabilities: {
    accountExportAvailable: boolean;
    accountDeletionAvailable: boolean;
    billingAvailable: boolean;
  }) => boolean;
};

const items: SettingsNavItem[] = [
  { href: "/settings", icon: UserRound, label: "Profile and account" },
  {
    href: "/settings/application-answers",
    icon: ClipboardList,
    label: "Application answers",
  },
  { href: "/settings/security", icon: KeyRound, label: "Security" },
  { href: "/settings/sessions", icon: Laptop, label: "Sessions" },
  { href: "/settings/notifications", icon: BellRing, label: "Notifications" },
  { href: "/settings/consent", icon: ShieldCheck, label: "Consent" },
  {
    href: "/settings/privacy",
    icon: ShieldCheck,
    label: "Privacy",
    visible: (capabilities) =>
      capabilities.accountExportAvailable ||
      capabilities.accountDeletionAvailable,
  },
  { href: "/settings/connections", icon: Link2, label: "Connections" },
  {
    href: "/settings/billing",
    icon: CreditCard,
    label: "Billing",
    visible: (capabilities) => capabilities.billingAvailable,
  },
];

export function SettingsNavigation() {
  const pathname = usePathname();
  const { capabilities } = useSettingsCapabilities();
  const visibleItems = items.filter(
    (item) =>
      !item.visible ||
      (capabilities &&
        item.visible({
          accountExportAvailable: capabilities.accountExportAvailable,
          accountDeletionAvailable: capabilities.accountDeletionAvailable,
          billingAvailable: capabilities.billingAvailable,
        })),
  );

  return (
    <nav
      aria-label="Settings navigation"
      className="overflow-x-auto rounded-[var(--radius-card)] border border-line bg-surface lg:overflow-visible"
    >
      <ul className="flex min-w-max gap-1 p-2 lg:block lg:min-w-0 lg:space-y-1">
        {visibleItems.map(({ href, icon: Icon, label }) => {
          const active = pathname === href;
          return (
            <li key={href}>
              <Link
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex min-h-11 items-center gap-2.5 rounded-xl px-3 text-sm font-semibold",
                  active
                    ? "bg-primary-soft/70 text-primary-strong"
                    : "text-muted hover:bg-surface-subtle hover:text-foreground",
                )}
                href={href}
              >
                <span
                  className={cn(
                    "grid size-8 shrink-0 place-items-center rounded-lg",
                    active
                      ? "bg-primary text-white"
                      : "bg-surface-subtle text-muted-strong",
                  )}
                >
                  <Icon aria-hidden="true" className="size-4" />
                </span>
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
