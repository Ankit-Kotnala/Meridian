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
      className="size-full"
      fill="none"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M12 2 22 12 12 22 2 12Z"
        stroke="currentColor"
        strokeLinejoin="round"
        strokeWidth={1.5}
      />
      <path
        d="M8 15.5V9l4 4 4-4v6.5"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
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
          "grid size-7 shrink-0 place-items-center",
          inverted ? "text-accent-strong" : "text-accent",
        )}
      >
        <RezumiMark />
      </span>
      {!compact && (
        <span
          className={cn(
            "text-sm uppercase tracking-[0.14em]",
            inverted ? "text-white" : "text-foreground",
          )}
        >
          Meridian
        </span>
      )}
    </Link>
  );
}
