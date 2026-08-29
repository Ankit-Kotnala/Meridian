"use client";

import { ArrowRight, Menu, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { buttonStyles, cn } from "@rezumi/ui";

import { RezumiLogo } from "@/shared/components/rezumi-logo";
import { ScrollProgress } from "@/shared/motion/scroll-progress";
import { ThemeToggle } from "@/shared/theme/theme-toggle";

const navigation = [
  { label: "Platform", href: "/#platform" },
  { label: "Workflow", href: "/#how-it-works" },
  { label: "Trust", href: "/#trust" },
  { label: "Preview", href: "/#availability" },
];

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    // The header stays pinned at all times; we only track whether the page has
    // scrolled so the bar can condense into its raised, blurred state.
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <>
      <header className="fixed inset-x-0 top-0 z-50">
        <div className="px-3">
          <div
            className={cn(
              "relative mx-auto flex items-center justify-between gap-4 overflow-hidden border transition-[max-width,margin,padding,background-color,border-color,box-shadow] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]",
              scrolled
                ? "mt-2 max-w-[62rem] rounded-2xl border-line/70 bg-surface-raised/80 px-3 py-2 shadow-[var(--shadow-lg)] backdrop-blur-xl backdrop-saturate-150 supports-[backdrop-filter]:bg-surface-raised/72"
                : "mt-4 max-w-[74rem] rounded-2xl border-line/45 bg-surface-raised/55 px-4 py-2.5 shadow-[var(--shadow-md)] backdrop-blur-lg backdrop-saturate-150 supports-[backdrop-filter]:bg-surface-raised/45",
            )}
          >
            <RezumiLogo />
            <nav
              aria-label="Primary navigation"
              className="hidden items-center gap-0.5 md:flex"
            >
              {navigation.map((item) => (
                <Link
                  className="rounded-full px-3.5 py-2 text-sm font-semibold text-muted transition-colors hover:bg-primary-soft/60 hover:text-foreground"
                  href={item.href}
                  key={item.label}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
            <div className="hidden items-center gap-2 md:flex">
              <ThemeToggle />
              <Link
                className={cn(
                  buttonStyles.base,
                  buttonStyles.ghost,
                  "min-h-10",
                )}
                href="/login"
              >
                Sign in
              </Link>
              <Link
                className={cn(
                  buttonStyles.base,
                  buttonStyles.primary,
                  "min-h-10",
                )}
                href="/demo/dashboard"
              >
                Explore demo
                <ArrowRight aria-hidden="true" className="size-4" />
              </Link>
            </div>
            <button
              aria-controls="mobile-navigation"
              aria-expanded={open}
              aria-label={
                open ? "Close navigation menu" : "Open navigation menu"
              }
              className="grid size-10 place-items-center rounded-[var(--radius-control)] border border-line bg-surface text-foreground shadow-sm transition-colors hover:border-primary/40 hover:bg-primary-soft/50 md:hidden"
              onClick={() => setOpen((value) => !value)}
              type="button"
            >
              {open ? (
                <X aria-hidden="true" className="size-5" />
              ) : (
                <Menu aria-hidden="true" className="size-5" />
              )}
            </button>

            {/* Scroll progress fills across the bottom edge of the bar. */}
            <ScrollProgress className="absolute inset-x-0 bottom-0 h-[3px]" />
          </div>

          {open && (
            <nav
              aria-label="Mobile navigation"
              className="mobile-nav-enter mx-auto mt-2 max-w-[62rem] overflow-hidden rounded-2xl border border-line bg-surface-raised/95 p-3 shadow-[var(--shadow-lg)] backdrop-blur-xl md:hidden"
              id="mobile-navigation"
            >
              <div className="grid gap-1">
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
                <div className="mt-3 flex items-center justify-between gap-2 border-t border-line pt-4">
                  <ThemeToggle />
                  <div className="grid flex-1 grid-cols-2 gap-2">
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
              </div>
            </nav>
          )}
        </div>
      </header>
      {/* Reserves the fixed header's footprint so page content starts below it. */}
      <div aria-hidden="true" className="h-[5.25rem]" />
    </>
  );
}
