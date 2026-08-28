import Link from "next/link";

import { cn } from "@rezumi/ui";

type RezumiLogoProps = {
  compact?: boolean;
  inverted?: boolean;
  className?: string;
  href?: string;
};

function RezumiMark() {
  return (
    <svg
      aria-hidden="true"
      className="size-[1.125rem]"
      fill="none"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M7.5 20V4h5a4 4 0 1 1 0 8h-5m4-3.5 6.5 11.5"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2.25}
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
          "grid size-9 shrink-0 place-items-center rounded-[var(--radius-control)]",
          inverted ? "bg-white/10 text-white" : "bg-primary-soft text-primary",
        )}
      >
        <RezumiMark />
      </span>
      {!compact && (
        <span
          className={cn(
            "text-[1.0625rem]",
            inverted ? "text-white" : "text-foreground",
          )}
        >
          Meridian
        </span>
      )}
    </Link>
  );
}
