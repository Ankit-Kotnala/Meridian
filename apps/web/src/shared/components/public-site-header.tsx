"use client";

import { ArrowRight, Menu, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { buttonStyles, cn } from "@careeros/ui";

import { CareerOsLogo } from "@/shared/components/career-os-logo";

const navigation = [
  { label: "Platform", href: "/#platform" },
  { label: "Workflow", href: "/#how-it-works" },
  { label: "Trust", href: "/#trust" },
  { label: "Preview", href: "/#availability" },
];

export function SiteHeader() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-border/90 bg-surface-raised/82 shadow-[0_1px_0_rgba(19,45,36,0.03)] backdrop-blur-xl">
      <div className="site-container flex h-[4.5rem] items-center justify-between gap-6">
        <CareerOsLogo />
        <nav
          aria-label="Primary navigation"
          className="hidden items-center gap-7 md:flex"
        >
          {navigation.map((item) => (
            <Link
              className="nav-link text-sm font-semibold text-muted transition-colors hover:text-foreground"
              href={item.href}
              key={item.label}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="hidden items-center gap-2 md:flex">
          <Link
            className={cn(buttonStyles.base, buttonStyles.ghost)}
            href="/login"
          >
            Sign in
          </Link>
          <Link
            className={cn(buttonStyles.base, buttonStyles.primary)}
            href="/demo/dashboard"
          >
            Explore demo
            <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
        </div>
        <button
          aria-controls="mobile-navigation"
          aria-expanded={open}
          aria-label={open ? "Close navigation menu" : "Open navigation menu"}
          className="grid size-11 place-items-center rounded-[var(--radius-control)] border border-line bg-white text-foreground shadow-sm md:hidden"
          onClick={() => setOpen((value) => !value)}
          type="button"
        >
          {open ? (
            <X aria-hidden="true" className="size-5" />
          ) : (
            <Menu aria-hidden="true" className="size-5" />
          )}
        </button>
      </div>
      {open && (
        <nav
          aria-label="Mobile navigation"
          className="mobile-nav-enter overflow-hidden border-t border-line bg-white/96 px-4 pb-5 pt-3 backdrop-blur-xl md:hidden"
          id="mobile-navigation"
        >
          <div className="mx-auto grid max-w-xl gap-1">
            {navigation.map((item) => (
              <Link
                className="rounded-[var(--radius-control)] px-3 py-3 text-sm font-bold text-foreground hover:bg-surface-subtle"
                href={item.href}
                key={item.label}
                onClick={() => setOpen(false)}
              >
                {item.label}
              </Link>
            ))}
            <div className="mt-3 grid grid-cols-2 gap-2 border-t border-line pt-4">
              <Link
                className={cn(buttonStyles.base, buttonStyles.secondary)}
                href="/login"
                onClick={() => setOpen(false)}
              >
                Sign in
              </Link>
              <Link
                className={cn(buttonStyles.base, buttonStyles.primary)}
                href="/demo/dashboard"
                onClick={() => setOpen(false)}
              >
                Explore demo
              </Link>
            </div>
          </div>
        </nav>
      )}
    </header>
  );
}
