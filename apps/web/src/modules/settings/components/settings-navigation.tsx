"use client";

import {
  BellRing,
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

import { cn } from "@careeros/ui";

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
      className="overflow-x-auto border-b border-line lg:sticky lg:top-21 lg:overflow-visible lg:border-b-0"
    >
      <ul className="flex min-w-max gap-1 lg:block lg:min-w-0 lg:space-y-0.5">
        {visibleItems.map(({ href, icon: Icon, label }) => {
          const active = pathname === href;
          return (
            <li key={href}>
              <Link
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex min-h-11 items-center gap-2 border-b-2 px-3 text-sm font-semibold lg:border-b-0 lg:border-l-2",
                  active
                    ? "border-primary bg-primary-soft/55 text-primary-strong"
                    : "border-transparent text-muted hover:bg-surface-subtle hover:text-foreground",
                )}
                href={href}
              >
                <Icon aria-hidden="true" className="size-4" /> {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
