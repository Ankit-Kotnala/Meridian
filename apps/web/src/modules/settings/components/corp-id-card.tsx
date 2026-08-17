"use client";

import {
  BadgeCheck,
  Check,
  CircleDashed,
  Copy,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useState } from "react";

import { Badge, Button, cn } from "@rezumi/ui";

import {
  CORP_ID_DISCLAIMER,
  corpIdFor,
  corpIdStanding,
  type CorpIdTier,
} from "@/shared/identity/corp-id";

import { getCorpIdChecks } from "../api/settings-api";

const TIER_ORDER: readonly CorpIdTier[] = [
  "unverified",
  "registered",
  "profiled",
  "evidenced",
];

const TIER_TONE: Record<CorpIdTier, "neutral" | "primary" | "success"> = {
  evidenced: "success",
  profiled: "primary",
  registered: "primary",
  unverified: "neutral",
};

const LADDER: readonly { label: string; tier: CorpIdTier }[] = [
  { label: "Email confirmed", tier: "registered" },
  { label: "Career record present", tier: "profiled" },
  { label: "Evidence confirmed", tier: "evidenced" },
];

export function CorpIdCard({
  emailVerified,
  userId,
}: {
  emailVerified: boolean;
  userId: string;
}) {
  const [checks, setChecks] = useState<{
    confirmedEvidence: number;
    experiences: number;
  }>();
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      void getCorpIdChecks().then((value) => {
        if (active) setChecks(value);
      });
    });
    return () => {
      active = false;
    };
  }, []);

  const corpId = corpIdFor(userId);
  if (!corpId) return null;

  const standing = corpIdStanding({
    confirmedEvidence: checks?.confirmedEvidence ?? 0,
    emailVerified,
    experiences: checks?.experiences ?? 0,
  });
  const reached = TIER_ORDER.indexOf(standing.tier);

  async function copy() {
    try {
      await navigator.clipboard.writeText(corpId ?? "");
      setCopied(true);
      globalThis.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  return (
    <section
      aria-labelledby="corp-id-heading"
      className="overflow-hidden rounded-[var(--radius-card)] border border-primary/25 bg-gradient-to-br from-primary-soft/60 via-surface to-accent-soft/35"
    >
      <div className="flex flex-wrap items-start justify-between gap-4 p-5 sm:p-6">
        <div className="min-w-0">
          <h2
            className="eyebrow flex items-center gap-1.5 !text-primary-strong"
            id="corp-id-heading"
          >
            <ShieldCheck aria-hidden="true" className="size-3.5" />
            Rezumi Corp ID
          </h2>
          <p className="mt-2.5 font-display text-2xl font-semibold tabular-nums tracking-[0.02em] text-foreground">
            {corpId}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Badge tone={TIER_TONE[standing.tier]}>
              <BadgeCheck aria-hidden="true" className="size-3.5" />
              {standing.label}
            </Badge>
            {checks === undefined && (
              <span className="text-xs text-muted">Checking standing…</span>
            )}
          </div>
        </div>
        <Button onClick={() => void copy()} variant="secondary">
          <Copy aria-hidden="true" className="size-4" />
          {copied ? "Copied" : "Copy ID"}
        </Button>
      </div>

      <div className="border-t border-primary/15 bg-surface/70 p-5 sm:p-6">
        <p className="text-sm leading-6 text-muted-strong">
          {standing.attests}
        </p>
        {standing.next && (
          <p className="mt-2 text-sm leading-6 text-muted">
            <span className="font-semibold text-foreground">Next: </span>
            {standing.next}
          </p>
        )}

        <ul className="mt-4 grid gap-2 sm:grid-cols-3">
          {LADDER.map(({ label, tier }) => {
            const met = reached >= TIER_ORDER.indexOf(tier);
            return (
              <li
                className="flex items-center gap-2 text-xs font-semibold"
                key={tier}
              >
                <span
                  className={cn(
                    "grid size-5 shrink-0 place-items-center rounded-full",
                    met
                      ? "bg-success-soft text-success-strong"
                      : "bg-surface-inset text-muted",
                  )}
                >
                  {met ? (
                    <Check aria-hidden="true" className="size-3" />
                  ) : (
                    <CircleDashed aria-hidden="true" className="size-3" />
                  )}
                </span>
                <span className={met ? "text-foreground" : "text-muted"}>
                  {label}
                </span>
                <span className="sr-only">
                  {met ? "complete" : "not yet complete"}
                </span>
              </li>
            );
          })}
        </ul>

        <p className="mt-4 border-t border-line pt-3 text-xs leading-5 text-muted">
          {CORP_ID_DISCLAIMER}
        </p>
      </div>
    </section>
  );
}
