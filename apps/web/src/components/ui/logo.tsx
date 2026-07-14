import { Orbit } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/cn";

type LogoProps = {
  compact?: boolean;
  inverted?: boolean;
  className?: string;
  href?: string;
};

export function Logo({
  compact = false,
  inverted = false,
  className,
  href = "/",
}: LogoProps) {
  return (
    <Link
      aria-label="CareerOS home"
      className={cn(
        "inline-flex items-center gap-2.5 rounded-lg font-extrabold tracking-[-0.03em]",
        className,
      )}
      href={href}
    >
      <span
        aria-hidden="true"
        className={cn(
          "grid size-9 shrink-0 place-items-center rounded-xl",
          inverted ? "bg-white/12 text-white" : "bg-primary-soft text-primary",
        )}
      >
        <Orbit className="size-5" strokeWidth={2.5} />
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
