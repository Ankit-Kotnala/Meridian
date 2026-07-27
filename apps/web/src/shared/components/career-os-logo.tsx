import { Waypoints } from "lucide-react";
import Link from "next/link";

import { cn } from "@careeros/ui";

type CareerOsLogoProps = {
  compact?: boolean;
  inverted?: boolean;
  className?: string;
  href?: string;
};

export function CareerOsLogo({
  compact = false,
  inverted = false,
  className,
  href = "/",
}: CareerOsLogoProps) {
  return (
    <Link
      aria-label="CareerOS home"
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
          inverted ? "bg-white/12 text-white" : "bg-primary-soft text-primary",
        )}
      >
        <Waypoints className="size-5" strokeWidth={2.25} />
      </span>
      {!compact && (
        <span
          className={cn(
            "text-[1.08rem]",
            inverted ? "text-white" : "text-foreground",
          )}
        >
          CareerOS
        </span>
      )}
    </Link>
  );
}
