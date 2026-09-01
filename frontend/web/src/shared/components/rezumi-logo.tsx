import Link from "next/link";

import { cn } from "@rezumi/ui";

type RezumiLogoProps = {
  /** Icon only — used in compact chrome such as a collapsed sidebar. */
  compact?: boolean;
  inverted?: boolean;
  className?: string;
  href?: string;
};

/**
 * Geometric Meridian mark (viewBox 0 0 100 100):
 * nested downward Vs between vertical legs. Diagonal endpoints are inset along
 * each stroke so butt caps sit inside the legs instead of forming corner horns.
 * Legs are painted last to keep the joins clean.
 */
export function RezumiMark({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={cn("size-full", className)}
      fill="none"
      viewBox="0 0 100 100"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M18 10 50 50 82 10"
        stroke="currentColor"
        strokeLinecap="butt"
        strokeLinejoin="miter"
        strokeWidth={8}
      />
      <path
        d="M18 54 50 90 82 54"
        stroke="currentColor"
        strokeLinecap="butt"
        strokeLinejoin="miter"
        strokeWidth={8}
      />
      <path
        d="M14 6v88"
        stroke="currentColor"
        strokeLinecap="butt"
        strokeWidth={8}
      />
      <path
        d="M86 6v88"
        stroke="currentColor"
        strokeLinecap="butt"
        strokeWidth={8}
      />
    </svg>
  );
}

export function RezumiLogo({
  compact = false,
  inverted = false,
  className,
  href = "/",
}: RezumiLogoProps) {
  return (
    <Link
      aria-label="Meridian home"
      className={cn(
        "inline-flex items-center gap-2.5 rounded-lg font-bold tracking-[-0.03em]",
        className,
      )}
      href={href}
    >
      <span
        aria-hidden="true"
        className={cn(
          "grid size-7 shrink-0 place-items-center overflow-hidden",
          inverted ? "text-[#aee2d9]" : "text-accent",
        )}
      >
        <RezumiMark />
      </span>
      {!compact && (
        <span
          className={cn(
            "text-sm uppercase tracking-[0.16em]",
            inverted ? "text-white" : "text-foreground",
          )}
        >
          Meridian
        </span>
      )}
    </Link>
  );
}
