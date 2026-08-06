"use client";

import { m } from "motion/react";
import type { ReactNode } from "react";

import { cn } from "@rezumi/ui";

export function Reveal({
  children,
  className,
  delay = 0,
  distance = 18,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  distance?: number;
}) {
  return (
    <m.div
      initial={{ opacity: 0, y: distance }}
      transition={{
        delay,
        duration: 0.52,
        ease: [0.22, 1, 0.36, 1],
      }}
      viewport={{
        amount: 0.18,
        margin: "0px 0px -8% 0px",
        once: true,
      }}
      whileInView={{ opacity: 1, y: 0 }}
      className={cn(className)}
    >
      {children}
    </m.div>
  );
}
