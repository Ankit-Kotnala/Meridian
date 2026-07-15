"use client";

import { Laptop, ShieldCheck, UserRound } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@careeros/ui";

const items = [
  { href: "/settings", icon: UserRound, label: "Profile and account" },
  { href: "/settings/sessions", icon: Laptop, label: "Sessions" },
  { href: "/settings/consent", icon: ShieldCheck, label: "Consent" },
] as const;

export function SettingsNavigation() {
  const pathname = usePathname();
  return (
    <nav aria-label="Settings navigation" className="overflow-x-auto">
      <ul className="flex min-w-max gap-2 border-b border-line">
        {items.map(({ href, icon: Icon, label }) => {
          const active = pathname === href;
          return (
            <li key={href}>
              <Link
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex min-h-11 items-center gap-2 border-b-2 px-3 text-sm font-bold",
                  active
                    ? "border-primary text-primary"
                    : "border-transparent text-muted hover:text-foreground",
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
