import {
  CheckCircle2,
  CircleHelp,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";

import { Badge, Card } from "@careeros/ui";

import type { EvidenceItem, EvidenceState, Provenance } from "../api/types";

const statePresentation: Record<
  EvidenceState,
  {
    description: string;
    label: string;
    tone: "danger" | "neutral" | "primary" | "success" | "warning";
  }
> = {
  verified: {
    description: "Checked through a documented CareerOS verification process.",
    label: "Verified",
    tone: "success",
  },
  confirmed: {
    description: "You explicitly confirmed this record and its scope.",
    label: "Confirmed",
    tone: "success",
  },
  supported: {
    description:
      "Directly supported by an authorized source within its exact wording.",
    label: "Supported",
    tone: "primary",
  },
  inferred: {
    description: "Interpreted from a source and awaiting your confirmation.",
    label: "Inferred",
    tone: "warning",
  },
  unsupported: {
    description: "No eligible source currently supports this record.",
    label: "Unsupported",
    tone: "danger",
  },
};

export function EvidenceStateBadge({ state }: { state: EvidenceState }) {
  const presentation = statePresentation[state];
  return (
    <span className="inline-flex flex-col items-start gap-1">
      <Badge tone={presentation.tone}>{presentation.label}</Badge>
      <span className="sr-only">{presentation.description}</span>
    </span>
  );
}

export function EvidenceEligibility({ evidence }: { evidence: EvidenceItem }) {
  const rows = [
    {
      eligible: evidence.factualEligible,
      label: "Factual use",
      text: evidence.factualEligible
        ? "Eligible within the exact supported scope"
        : "Not eligible for factual generation",
    },
    {
      eligible: evidence.numericEligible,
      label: "Numeric use",
      text: evidence.numericEligible
        ? "Eligible for confirmed numeric claims"
        : "Not eligible for generated numeric claims",
    },
  ];
  return (
    <Card
      className="grid gap-3 p-4 sm:grid-cols-2"
      aria-label="Generation eligibility"
    >
      {rows.map((row) => (
        <div className="flex items-start gap-2" key={row.label}>
          {row.eligible ? (
            <CheckCircle2
              aria-hidden="true"
              className="mt-0.5 size-4 text-success"
            />
          ) : (
            <TriangleAlert
              aria-hidden="true"
              className="mt-0.5 size-4 text-warning"
            />
          )}
          <div>
            <p className="text-xs font-extrabold uppercase tracking-wide text-muted">
              {row.label}
            </p>
            <p className="mt-1 text-sm font-bold text-foreground">{row.text}</p>
          </div>
        </div>
      ))}
    </Card>
  );
}

export function ProvenanceList({ values }: { values: Provenance[] }) {
  if (values.length === 0) {
    return (
      <p className="flex items-start gap-2 text-sm text-muted">
        <CircleHelp aria-hidden="true" className="mt-0.5 size-4" /> No source
        provenance is attached yet.
      </p>
    );
  }
  return (
    <ul className="space-y-3" aria-label="Source provenance">
      {values.map((value) => (
        <li
          className="rounded-xl border border-line bg-surface-subtle p-4"
          key={value.id}
        >
          <div className="flex flex-wrap items-center gap-2">
            <ShieldCheck aria-hidden="true" className="size-4 text-primary" />
            <p className="text-sm font-extrabold">{value.sourceLabel}</p>
            <Badge tone={value.userConfirmed ? "success" : "warning"}>
              {value.userConfirmed ? "User confirmed" : "Not confirmed"}
            </Badge>
            {!value.available && (
              <Badge tone="warning">Source unavailable</Badge>
            )}
          </div>
          <p className="mt-2 text-xs text-muted">
            Source type: {value.sourceType}
            {value.confidence === null
              ? " · extraction confidence unavailable"
              : ` · extraction confidence ${value.confidence}%`}
          </p>
          {value.spans.map((span) => (
            <blockquote
              className="mt-3 border-l-2 border-primary/30 pl-3 text-sm leading-6 text-muted"
              key={span.id}
            >
              {span.excerpt || "Source text is unavailable."}
              {span.page ? ` (page ${span.page})` : ""}
            </blockquote>
          ))}
        </li>
      ))}
    </ul>
  );
}
