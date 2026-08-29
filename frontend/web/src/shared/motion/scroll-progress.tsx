"use client";

import { useEffect, useState } from "react";

import { cn } from "@rezumi/ui";

/**
 * Thin gradient bar that fills as the page scrolls. Uses a GPU `scaleX`
 * transform updated inside a single rAF per scroll burst so it tracks the
 * scroll position 1:1 without layout thrash. By default it pins to the very top
 * of the viewport, but pass `className` to host it elsewhere (e.g. across the
 * bottom edge of the site header).
 */
export function ScrollProgress({ className }: { className?: string }) {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const el = document.documentElement;
      const max = el.scrollHeight - el.clientHeight;
      setProgress(max > 0 ? Math.min(1, el.scrollTop / max) : 0);
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      if (frame) cancelAnimationFrame(frame);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);

  return (
    <div
      aria-hidden="true"
      className={cn(
        "pointer-events-none",
        className ?? "fixed inset-x-0 top-0 z-[70] h-[3px]",
      )}
    >
      <div
        className="h-full w-full origin-left bg-gradient-to-r from-primary via-accent to-primary-strong shadow-[0_0_12px_color-mix(in_srgb,var(--accent)_55%,transparent)] transition-transform duration-150 ease-out"
        style={{ transform: `scaleX(${progress})` }}
      />
    </div>
  );
}
