"use client";

import { useEffect, useRef, useState, type MouseEvent } from "react";

import { Card, cn } from "@rezumi/ui";

export type ProfileSectionLink = {
  id: string;
  label: string;
};

export const profileSectionLinks: readonly ProfileSectionLink[] = [
  { id: "overview", label: "Overview" },
  { id: "employment", label: "Employment" },
  { id: "contact", label: "Contact" },
  { id: "education", label: "Education & projects" },
  { id: "skills", label: "Skills" },
];

/**
 * Pixels of sticky chrome (workspace header plus section tabs) a section has to
 * clear to be readable. Kept in sync with `scroll-mt` on the profile panels so
 * a link click and a `#hash` landing settle in the same place.
 */
export const sectionScrollOffset = 132;

function activeSectionId(): string {
  const documentElement = document.documentElement;
  const atBottom =
    window.scrollY + window.innerHeight >= documentElement.scrollHeight - 2;
  if (atBottom) return profileSectionLinks.at(-1)?.id ?? "";

  let current = profileSectionLinks[0]?.id ?? "";
  for (const { id } of profileSectionLinks) {
    const element = document.getElementById(id);
    if (!element) continue;
    if (element.getBoundingClientRect().top - sectionScrollOffset <= 8) {
      current = id;
    }
  }
  return current;
}

/**
 * In-page navigation for the profile record sections.
 *
 * Clicking scrolls explicitly rather than relying on the default anchor jump,
 * because the workspace header is sticky and a native jump lands the heading
 * underneath it. The scroll spy is suppressed while that animation runs — it
 * otherwise re-highlights whichever section passes through the viewport on the
 * way, which reads as the rail flickering back to the wrong entry.
 */
export function ProfileSideNav({
  completedCount,
  totalCount,
}: {
  completedCount: number;
  totalCount: number;
}) {
  const [activeId, setActiveId] = useState(profileSectionLinks[0]?.id ?? "");
  const spyLocked = useRef(false);
  const unlockTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    function sync() {
      if (spyLocked.current) return;
      setActiveId(activeSectionId());
    }
    sync();
    window.addEventListener("scroll", sync, { passive: true });
    window.addEventListener("resize", sync);
    return () => {
      window.removeEventListener("scroll", sync);
      window.removeEventListener("resize", sync);
      if (unlockTimer.current) clearTimeout(unlockTimer.current);
    };
  }, []);

  function goToSection(event: MouseEvent<HTMLAnchorElement>, id: string) {
    const target = document.getElementById(id);
    if (!target) return;
    event.preventDefault();
    setActiveId(id);
    spyLocked.current = true;
    if (unlockTimer.current) clearTimeout(unlockTimer.current);
    unlockTimer.current = setTimeout(() => {
      spyLocked.current = false;
    }, 1_000);
    const smooth = !window.matchMedia("(prefers-reduced-motion: reduce)")
      .matches;
    window.scrollTo({
      behavior: smooth ? "smooth" : "auto",
      top: Math.max(
        0,
        target.getBoundingClientRect().top +
          window.scrollY -
          sectionScrollOffset,
      ),
    });
    window.history.replaceState(null, "", `#${id}`);
    // Move reading focus with the scroll without stealing it back to the top.
    target.setAttribute("tabindex", "-1");
    target.focus({ preventScroll: true });
  }

  const percent =
    totalCount === 0 ? 0 : Math.round((completedCount / totalCount) * 100);

  return (
    <Card
      as="aside"
      aria-label="Career profile sections"
      className="sticky top-[8.5rem] p-4"
    >
      <p className="text-[0.8125rem] font-bold text-foreground">
        {completedCount} of {totalCount}{" "}
        <span className="font-semibold text-muted">complete</span>
      </p>
      <div
        aria-hidden="true"
        className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-inset"
      >
        <div
          className="h-full rounded-full bg-info transition-[width] duration-300 motion-reduce:transition-none"
          style={{ width: `${percent}%` }}
        />
      </div>
      <nav aria-label="Career profile sections" className="mt-4">
        <ul className="space-y-0.5">
          {profileSectionLinks.map((link) => {
            const active = activeId === link.id;
            return (
              <li key={link.id}>
                <a
                  {...(active ? { "aria-current": "true" as const } : {})}
                  className={cn(
                    "flex min-h-9 items-center gap-2 rounded-[var(--radius-control)] px-2 text-[0.8125rem] transition-colors",
                    active
                      ? "font-bold text-info"
                      : "font-semibold text-muted hover:bg-surface-subtle hover:text-foreground",
                  )}
                  href={`#${link.id}`}
                  onClick={(event) => goToSection(event, link.id)}
                >
                  <span
                    aria-hidden="true"
                    className={cn(
                      "size-1.5 shrink-0 rounded-full",
                      active ? "bg-info" : "bg-transparent",
                    )}
                  />
                  {link.label}
                </a>
              </li>
            );
          })}
        </ul>
      </nav>
    </Card>
  );
}
