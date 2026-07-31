"use client";

import { ArrowUp } from "lucide-react";
import { useEffect, useState } from "react";

import { cn } from "@careeros/ui";

/** Floating control that fades in after the reader scrolls past the fold. */
export function BackToTop() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > 640);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <button
      aria-hidden={!visible}
      aria-label="Back to top"
      className={cn(
        "fixed bottom-6 right-6 z-40 grid size-11 place-items-center rounded-full border border-line bg-surface-raised/85 text-primary-strong shadow-[var(--shadow-lg)] backdrop-blur-md transition-[opacity,transform] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] hover:-translate-y-0.5 hover:border-primary/45 hover:text-primary",
        visible
          ? "translate-y-0 opacity-100"
          : "pointer-events-none translate-y-3 opacity-0",
      )}
      onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
      tabIndex={visible ? 0 : -1}
      type="button"
    >
      <ArrowUp aria-hidden="true" className="size-5" />
    </button>
  );
}
