"use client";

import { ArrowRight, Menu, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { buttonStyles, cn } from "@careeros/ui";

import { CareerOsLogo } from "@/shared/components/career-os-logo";
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
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    let lastY = window.scrollY;
    // Accumulate continuous travel in one direction so the header only tucks
    // away after a deliberate scroll, not on every small twitch.
    let downTravel = 0;
    let upTravel = 0;

    const onScroll = () => {
      const y = window.scrollY;
      setScrolled(y > 8);

      const nearBottom =
        y + window.innerHeight >= document.documentElement.scrollHeight - 120;
      const goingDown = y > lastY;

      if (goingDown) {
        downTravel += y - lastY;
        upTravel = 0;
      } else {
        upTravel += lastY - y;
        downTravel = 0;
      }

      if (y < 120) {
        setHidden(false);
      } else if (nearBottom || downTravel > 64) {
        setHidden(true);
      } else if (upTravel > 24) {
        setHidden(false);
      }

      lastY = y;
    };

    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const tucked = hidden && !open;

  return (
    <>
      <ScrollProgress />
      <header
        className={cn(
          "fixed inset-x-0 top-0 z-50 origin-top transform-gpu transition-[transform,opacity] duration-500 ease-[cubic-bezier(0.33,1,0.68,1)] will-change-transform motion-reduce:transition-none",
          tucked
            ? "-translate-y-[calc(100%+1.5rem)] scale-[0.98] opacity-0"
            : "translate-y-0 scale-100 opacity-100",
        )}
      >
        <div className={cn("px-3", tucked && "pointer-events-none")}>
          <div
            className={cn(
              "mx-auto flex items-center justify-between gap-4 border transition-[max-width,margin,padding,background-color,border-color,box-shadow] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]",
              scrolled
                ? "mt-2 max-w-[62rem] rounded-2xl border-line/70 bg-surface-raised/80 px-3 py-2 shadow-[var(--shadow-lg)] backdrop-blur-xl backdrop-saturate-150 supports-[backdrop-filter]:bg-surface-raised/72"
                : "mt-4 max-w-[74rem] rounded-2xl border-line/45 bg-surface-raised/55 px-4 py-2.5 shadow-[var(--shadow-md)] backdrop-blur-lg backdrop-saturate-150 supports-[backdrop-filter]:bg-surface-raised/45",
            )}
          >
            <CareerOsLogo />
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
                className={cn(buttonStyles.base, buttonStyles.ghost, "min-h-10")}
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
