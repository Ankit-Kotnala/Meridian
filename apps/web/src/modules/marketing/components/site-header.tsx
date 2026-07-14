"use client";

import { ArrowRight, Menu, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { buttonStyles, cn } from "@careeros/ui";

import { CareerOsLogo } from "@/shared/components/career-os-logo";

const navigation = [
  { label: "Product", href: "/#product" },
  { label: "How it works", href: "/#how-it-works" },
  { label: "Trust", href: "/#trust" },
  { label: "Pricing", href: "/#pricing" },
];

export function SiteHeader() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-line/80 bg-white/90 backdrop-blur-xl">
      <div className="site-container flex h-17 items-center justify-between gap-6">
        <CareerOsLogo />
        <nav
          aria-label="Primary navigation"
          className="hidden items-center gap-7 md:flex"
        >
          {navigation.map((item) => (
            <Link
              className="text-sm font-semibold text-muted transition hover:text-foreground"
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
            href="/dashboard"
          >
            Explore the demo
            <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
        </div>
        <button
          aria-controls="mobile-navigation"
          aria-expanded={open}
          aria-label={open ? "Close navigation menu" : "Open navigation menu"}
          className="grid size-10 place-items-center rounded-xl border border-line bg-white text-foreground md:hidden"
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
          className="border-t border-line bg-white px-4 pb-5 pt-3 md:hidden"
          id="mobile-navigation"
        >
          <div className="mx-auto grid max-w-xl gap-1">
            {navigation.map((item) => (
              <Link
                className="rounded-xl px-3 py-3 text-sm font-bold text-foreground hover:bg-slate-50"
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
                href="/dashboard"
                onClick={() => setOpen(false)}
              >
                View demo
              </Link>
            </div>
          </div>
        </nav>
      )}
    </header>
  );
}
