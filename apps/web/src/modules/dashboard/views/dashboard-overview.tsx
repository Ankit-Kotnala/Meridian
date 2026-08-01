import {
  ArrowRight,
  Check,
  FileSearch,
  GitCompareArrows,
  LockKeyhole,
  UserRoundCheck,
} from "lucide-react";
import Link from "next/link";

import { Badge, buttonStyles, cn, DefinitionList } from "@careeros/ui";

const scenarioSteps = [
  {
    description:
      "A fictional profile contains reviewed career facts and links to eligible supporting records.",
    icon: UserRoundCheck,
    label: "Begin with career truth",
  },
  {
    description:
      "An illustrative opportunity adds role requirements without becoming a source of career claims.",
    icon: FileSearch,
    label: "Add opportunity context",
  },
  {
    description:
      "CareerOS can propose a change, but the original, reason, evidence, and requirement stay visible.",
    icon: GitCompareArrows,
    label: "Review the proposed change",
  },
  {
    description:
      "Accepted work can become a new document version. Published exports remain immutable.",
    icon: LockKeyhole,
    label: "Publish intentionally",
  },
] as const;

export function DashboardOverview() {
  return (
    <main className="site-container py-10 sm:py-14" id="main-content">
      <div className="flex flex-col gap-3 border-b border-line pb-7 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Badge tone="warning">
            Fictional demo data · product preview only
          </Badge>
          <h1 className="mt-4 font-display text-3xl font-semibold tracking-[-0.04em] sm:text-4xl">
            Good morning, Jordan Lee
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">
            Jordan is a fictional persona. This guided view explains how
            CareerOS connects career facts, evidence, requirements, and
            controlled outputs without presenting invented performance data.
          </p>
        </div>
        <Link className="text-link text-sm" href="/">
          Return to product overview
        </Link>
      </div>

      <section aria-labelledby="scenario-heading" className="py-10">
        <div className="grid gap-8 lg:grid-cols-[0.7fr_1.3fr]">
          <header>
            <p className="eyebrow">Guided scenario</p>
            <h2
              className="mt-3 font-display text-2xl font-semibold tracking-[-0.03em]"
              id="scenario-heading"
            >
              Follow the evidence into an output.
            </h2>
            <p className="mt-3 text-sm leading-6 text-muted">
              This is an operating-model walkthrough, not an activity feed or
              claim about a real job search.
            </p>
          </header>
          <ol className="border-l border-line">
            {scenarioSteps.map(({ description, icon: Icon, label }, index) => (
              <li className="relative pb-7 pl-8 last:pb-0" key={label}>
                <span className="absolute -left-4 top-0 grid size-8 place-items-center rounded-full border border-line-strong bg-surface text-primary">
                  <Icon aria-hidden="true" className="size-4" />
                </span>
                <p className="text-xs font-bold uppercase tracking-[0.08em] text-muted">
                  Step {index + 1}
                </p>
                <h3 className="mt-1 font-semibold text-foreground">{label}</h3>
                <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">
                  {description}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section
        aria-labelledby="decision-heading"
        className="grid gap-7 border-y border-line py-9 lg:grid-cols-[1fr_1fr]"
      >
        <div>
          <p className="eyebrow">Illustrative review state</p>
          <h2
            className="mt-3 text-xl font-semibold tracking-[-0.025em]"
            id="decision-heading"
          >
            A material change waits for a person.
          </h2>
          <p className="mt-3 text-sm leading-6 text-muted">
            The product never silently replaces career-document content. A
            review state preserves what changed and why, then offers explicit
            accept, reject, or edit paths in the authenticated workflow.
          </p>
          <Link
            className="text-link mt-4 inline-flex text-sm"
            href="/responsible-ai"
          >
            Read the responsible AI policy
          </Link>
        </div>
        <div className="rounded-[var(--radius-card)] border border-primary/25 bg-primary-soft/35 p-5">
          <div className="flex items-center gap-2">
            <span className="grid size-7 place-items-center rounded-full bg-primary text-white">
              <Check aria-hidden="true" className="size-4" />
            </span>
            <h3 className="font-semibold text-foreground">Review includes</h3>
          </div>
          <DefinitionList
            className="mt-4 border-primary/15 bg-surface/70"
            items={[
              { label: "Original", value: "The current document language" },
              { label: "Proposal", value: "The suggested language" },
              { label: "Reason", value: "Why the change may help" },
              { label: "Evidence", value: "Eligible source links" },
              { label: "Requirement", value: "Relevant opportunity context" },
            ]}
          />
        </div>
      </section>

      <section aria-labelledby="limits-heading" className="py-10">
        <div className="grid gap-6 md:grid-cols-[0.8fr_1.2fr]">
          <h2
            className="font-display text-2xl font-semibold tracking-[-0.03em]"
            id="limits-heading"
          >
            What the measurements mean
          </h2>
          <div>
            <p className="text-sm leading-7 text-muted">
              CareerOS measurements are internal, explainable decision-support
              signals. They are not scores provided by an employer or applicant
              tracking system, hiring probabilities, or outcome guarantees.
            </p>
            <Link
              className="text-link mt-4 inline-flex text-sm"
              href="/methodology"
            >
              Read the scoring methodology
            </Link>
          </div>
        </div>
      </section>

      <section className="flex flex-col gap-5 rounded-[var(--radius-card)] bg-navy px-6 py-7 text-white sm:flex-row sm:items-center sm:justify-between sm:px-8">
        <div>
          <h2 className="text-xl font-semibold">
            Ready to test the real flow?
          </h2>
          <p className="mt-1 text-sm text-emerald-50/70">
            Use fictional or non-sensitive content during the technical preview.
          </p>
        </div>
        <Link
          className={cn(
            buttonStyles.base,
            "bg-white text-navy hover:bg-surface-subtle",
          )}
          href="/get-started"
        >
          Choose how to start
          <ArrowRight aria-hidden="true" className="size-4" />
        </Link>
      </section>
    </main>
  );
}
