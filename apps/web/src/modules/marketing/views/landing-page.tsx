import {
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  Database,
  FileCheck2,
  FileText,
  GitBranch,
  Layers3,
  LockKeyhole,
  MessageSquareText,
  SearchCheck,
  ShieldCheck,
  UserRoundCheck,
} from "lucide-react";
import Link from "next/link";

import { Badge, buttonStyles, cn } from "@careeros/ui";

import { BackToTop } from "@/shared/components/back-to-top";
import { SiteFooter } from "@/shared/components/public-site-footer";
import { SiteHeader } from "@/shared/components/public-site-header";
import { ProductMotionProvider } from "@/shared/motion/product-motion-provider";
import { Reveal } from "@/shared/motion/reveal";

const systemLayers = [
  {
    description:
      "Roles, projects, skills, achievements, preferences, and review state live in one durable record.",
    icon: Database,
    label: "Career record",
    meta: "Source of truth",
  },
  {
    description:
      "Every eligible source stays connected to the factual claim it can support.",
    icon: GitBranch,
    label: "Evidence graph",
    meta: "Provenance layer",
  },
  {
    description:
      "Role context and job requirements shape analysis without rewriting the underlying facts.",
    icon: SearchCheck,
    label: "Decision context",
    meta: "Explainable analysis",
  },
  {
    description:
      "Resumes, answers, stories, and messages remain reviewable before they become final.",
    icon: FileCheck2,
    label: "Controlled outputs",
    meta: "User approved",
  },
] as const;

const workflow = [
  {
    description:
      "Start directly or import a resume. Uncertain details are held for review instead of silently becoming truth.",
    label: "Establish the record",
  },
  {
    description:
      "Connect supporting material and confirm which claims are eligible for future generation.",
    label: "Qualify the evidence",
  },
  {
    description:
      "Add a role or exact job context and see the requirement behind every recommendation.",
    label: "Set the opportunity",
  },
  {
    description:
      "Inspect the original, proposed change, reason, and evidence before you accept or reject it.",
    label: "Approve the output",
  },
] as const;

const trustControls = [
  {
    description:
      "Missing facts create a question. Unsupported evidence never becomes generation input.",
    icon: MessageSquareText,
    title: "Grounded by default",
  },
  {
    description:
      "Every user-owned resource is resolved through its ownership scope, not an identifier alone.",
    icon: LockKeyhole,
    title: "Ownership-aware access",
  },
  {
    description:
      "Material changes preserve the original, reason, evidence, requirement, and explicit decision.",
    icon: UserRoundCheck,
    title: "Approval is part of the model",
  },
] as const;

const outputs = [
  {
    description: "Structured facts and review state",
    icon: Database,
    title: "Career profile",
  },
  {
    description: "Requirements and approved documents",
    icon: FileText,
    title: "Applications",
  },
  {
    description: "Evidence-backed narrative material",
    icon: MessageSquareText,
    title: "Interview stories",
  },
  {
    description: "Learning and achievement continuity",
    icon: Layers3,
    title: "Growth record",
  },
] as const;

const faqs = [
  [
    "Does CareerOS know an employer's ATS score?",
    "No. CareerOS uses internal, explainable measurements for specific questions. They are not employer or applicant-tracking-system scores and do not guarantee outcomes.",
  ],
  [
    "Will CareerOS invent stronger achievements?",
    "No. If a useful detail is missing, CareerOS asks for it. Unsupported evidence is not generation input, and numbers need confirmed or independently verified support.",
  ],
  [
    "Do I need a resume to start?",
    "No. You can build a structured career profile directly. A resume can accelerate setup, but reviewed structured data becomes the lasting source of truth.",
  ],
  [
    "Is this a production service?",
    "Not yet. CareerOS is a technical product preview. Public legal notices, support channels, and commercial plans remain launch requirements.",
  ],
] as const;

function ProductWorkspacePreview() {
  const recordRows = [
    ["Role history", "Reviewed", true],
    ["Achievement context", "Evidence needed", false],
    ["Skills and tools", "Reviewed", true],
  ] as const;

  return (
    <figure className="preview-float relative mx-auto w-full max-w-[46rem]">
      <div className="overflow-hidden rounded-[1.1rem] border border-navy/15 bg-surface shadow-[0_26px_70px_-34px_rgba(19,45,36,0.42)]">
        <div className="flex h-12 items-center justify-between border-b border-line bg-surface-subtle px-4">
          <div aria-hidden="true" className="flex items-center gap-2">
            <span className="size-2 rounded-full bg-border-strong" />
            <span className="size-2 rounded-full bg-border-strong" />
            <span className="size-2 rounded-full bg-border-strong" />
          </div>
          <div className="flex items-center gap-2 text-[0.6875rem] font-semibold text-muted">
            <ShieldCheck aria-hidden="true" className="size-3.5 text-primary" />
            Fictional product interface
          </div>
        </div>

        <div className="grid min-h-[28rem] grid-cols-1 sm:grid-cols-[9rem_minmax(0,1fr)]">
          <div className="hidden bg-navy px-3 py-5 text-white sm:block">
            <div className="flex items-center gap-2 px-2 text-xs font-bold">
              <span className="grid size-6 place-items-center rounded-md bg-white/10">
                <Layers3 aria-hidden="true" className="size-3.5" />
              </span>
              CareerOS
            </div>
            <div className="mt-7">
              {["Overview", "Career record", "Evidence", "Opportunities"].map(
                (item, index) => (
                  <div
                    className={cn(
                      "mb-1 rounded-md px-2.5 py-2 text-[0.6875rem]",
                      index === 1
                        ? "bg-white/10 font-semibold text-white"
                        : "text-emerald-50/55",
                    )}
                    key={item}
                  >
                    {item}
                  </div>
                ),
              )}
            </div>
            <div className="mt-20 border-t border-white/10 px-2 pt-4 text-[0.625rem] leading-4 text-emerald-50/45">
              Private workspace
              <br />
              Approval required
            </div>
          </div>

          <div className="min-w-0 bg-[#f8faf8] p-4 sm:p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[0.625rem] font-bold uppercase tracking-[0.12em] text-primary">
                  Career record
                </p>
                <h2 className="mt-1 text-lg font-semibold tracking-[-0.025em] text-foreground">
                  Review workspace
                </h2>
              </div>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[0.625rem] font-bold text-amber-800">
                <CircleDot aria-hidden="true" className="size-3" />
                Review in progress
              </span>
            </div>

            <div className="mt-5 grid gap-3 lg:grid-cols-[minmax(0,1fr)_12rem]">
              <section className="rounded-xl border border-line bg-surface">
                <div className="flex items-center justify-between border-b border-line px-4 py-3">
                  <div>
                    <h3 className="text-xs font-semibold text-foreground">
                      Structured record
                    </h3>
                    <p className="mt-0.5 text-[0.625rem] text-muted">
                      Facts stay separate from generated wording
                    </p>
                  </div>
                  <Database
                    aria-hidden="true"
                    className="size-4 text-primary"
                  />
                </div>
                <div className="divide-y divide-line">
                  {recordRows.map(([label, status, complete]) => (
                    <div
                      className="flex items-center gap-3 px-4 py-3"
                      key={label}
                    >
                      <span
                        className={cn(
                          "grid size-7 shrink-0 place-items-center rounded-md",
                          complete
                            ? "bg-primary-soft text-primary"
                            : "bg-amber-50 text-amber-700",
                        )}
                      >
                        {complete ? (
                          <CheckCircle2
                            aria-hidden="true"
                            className="size-3.5"
                          />
                        ) : (
                          <MessageSquareText
                            aria-hidden="true"
                            className="size-3.5"
                          />
                        )}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[0.6875rem] font-semibold text-foreground">
                          {label}
                        </span>
                        <span className="mt-0.5 block text-[0.625rem] text-muted">
                          {status}
                        </span>
                      </span>
                      <ChevronRight
                        aria-hidden="true"
                        className="size-3.5 text-muted"
                      />
                    </div>
                  ))}
                </div>
              </section>

              <section className="rounded-xl border border-line bg-surface p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[0.625rem] font-bold uppercase tracking-[0.1em] text-muted">
                      Change review
                    </p>
                    <h3 className="mt-1 text-xs font-semibold text-foreground">
                      Awaiting your decision
                    </h3>
                  </div>
                  <FileCheck2
                    aria-hidden="true"
                    className="size-4 text-primary"
                  />
                </div>
                <dl className="mt-4 space-y-3 text-[0.625rem]">
                  <div>
                    <dt className="font-semibold text-muted">Original</dt>
                    <dd className="mt-1 rounded-md bg-surface-subtle px-2 py-1.5 text-foreground">
                      Draft statement
                    </dd>
                  </div>
                  <div>
                    <dt className="font-semibold text-muted">Proposed</dt>
                    <dd className="mt-1 rounded-md border border-primary/20 bg-primary-soft px-2 py-1.5 text-foreground">
                      Evidence-linked revision
                    </dd>
                  </div>
                </dl>
                <div className="mt-4 flex items-center gap-1.5 border-t border-line pt-3 text-[0.625rem] font-semibold text-primary">
                  <GitBranch aria-hidden="true" className="size-3" />
                  Provenance available
                </div>
              </section>
            </div>

            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <div className="flex items-center gap-3 rounded-lg border border-line bg-surface px-3 py-2.5">
                <span className="grid size-7 place-items-center rounded-md bg-primary-soft text-primary">
                  <SearchCheck aria-hidden="true" className="size-3.5" />
                </span>
                <span>
                  <span className="block text-[0.625rem] font-bold text-foreground">
                    Requirement linked
                  </span>
                  <span className="block text-[0.5625rem] text-muted">
                    Reason stays visible
                  </span>
                </span>
              </div>
              <div className="flex items-center gap-3 rounded-lg border border-line bg-surface px-3 py-2.5">
                <span className="grid size-7 place-items-center rounded-md bg-primary-soft text-primary">
                  <ShieldCheck aria-hidden="true" className="size-3.5" />
                </span>
                <span>
                  <span className="block text-[0.625rem] font-bold text-foreground">
                    Approval controlled
                  </span>
                  <span className="block text-[0.5625rem] text-muted">
                    Nothing publishes silently
                  </span>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
      <figcaption className="mt-3 text-center text-[0.6875rem] leading-5 text-muted">
        Illustrative interface only. It contains no customer data or performance
        claims.
      </figcaption>
    </figure>
  );
}

export function LandingPage() {
  return (
    <ProductMotionProvider>
      <div className="min-h-screen bg-background text-foreground">
        <SiteHeader />
        <main id="main-content">
          <section className="ambient-canvas relative overflow-hidden border-b border-line">
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 overflow-hidden"
            >
              <div className="absolute -left-24 -top-24 size-[26rem] rounded-full bg-[radial-gradient(circle,color-mix(in_srgb,var(--accent-soft)_85%,transparent),transparent_70%)] blur-2xl motion-safe:animate-[orb-drift_16s_var(--ease-standard)_infinite]" />
              <div className="absolute -bottom-32 right-[-6rem] size-[30rem] rounded-full bg-[radial-gradient(circle,color-mix(in_srgb,var(--primary-soft)_80%,transparent),transparent_70%)] blur-2xl motion-safe:animate-[orb-drift_22s_var(--ease-standard)_infinite_reverse]" />
            </div>
            <div
              aria-hidden="true"
              className="absolute inset-y-0 right-0 hidden w-[42%] border-l border-line bg-surface/38 backdrop-blur-[2px] lg:block"
            />
            <div className="site-container relative grid gap-12 py-14 sm:py-20 lg:grid-cols-[minmax(0,0.82fr)_minmax(32rem,1.18fr)] lg:items-center lg:gap-14 lg:py-24">
              <Reveal>
                <div className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-[0.12em] text-primary">
                  <span className="h-px w-6 bg-primary" />
                  Evidence-first career operations
                </div>
                <h1 className="balanced mt-6 max-w-3xl font-display text-[2.75rem] font-semibold leading-[1.02] tracking-[-0.05em] text-foreground sm:text-6xl lg:text-[4.25rem]">
                  The system of record behind your career.
                </h1>
                <p className="mt-6 max-w-xl text-lg leading-8 text-muted">
                  Bring career facts, supporting evidence, opportunity context,
                  and every approved output into one controlled workspace.
                </p>
                <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                  <Link
                    className={cn(buttonStyles.base, buttonStyles.primary)}
                    href="/demo/dashboard"
                  >
                    Explore the fictional demo
                    <ArrowRight aria-hidden="true" className="size-4" />
                  </Link>
                  <Link
                    className={cn(buttonStyles.base, buttonStyles.secondary)}
                    href="/#platform"
                  >
                    See the platform
                  </Link>
                </div>
                <p className="mt-5 flex max-w-lg items-start gap-2 text-xs leading-5 text-muted">
                  <LockKeyhole
                    aria-hidden="true"
                    className="mt-0.5 size-3.5 shrink-0 text-primary"
                  />
                  Technical preview. Use fictional or non-sensitive content
                  while production legal and support controls are completed.
                </p>
              </Reveal>
              <Reveal className="min-w-0" delay={0.12} distance={24}>
                <ProductWorkspacePreview />
              </Reveal>
            </div>
          </section>

          <section
            aria-label="Core product controls"
            className="border-b border-line bg-navy text-white"
          >
            <div className="site-container grid divide-y divide-white/10 sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-4">
              {[
                "No unsupported claims",
                "Approval before material edits",
                "Ownership-scoped data",
                "Immutable published versions",
              ].map((item) => (
                <div
                  className="flex min-h-16 items-center gap-2.5 px-1 py-4 text-xs font-semibold sm:px-5"
                  key={item}
                >
                  <CheckCircle2
                    aria-hidden="true"
                    className="size-4 shrink-0 text-emerald-300"
                  />
                  {item}
                </div>
              ))}
            </div>
          </section>

          <section
            className="landing-section site-container py-16 sm:py-24"
            id="platform"
          >
            <div className="grid gap-12 lg:grid-cols-[0.68fr_1.32fr] lg:gap-16">
              <header className="lg:sticky lg:top-28 lg:self-start">
                <p className="eyebrow">Platform architecture</p>
                <h2 className="balanced mt-3 font-display text-3xl font-semibold tracking-[-0.04em] sm:text-4xl">
                  One source of truth. Every workflow downstream.
                </h2>
                <p className="mt-5 text-sm leading-7 text-muted">
                  CareerOS separates facts, evidence, context, and generated
                  wording so each layer can be inspected without corrupting the
                  others.
                </p>
                <Link
                  className="text-link mt-6 inline-flex items-center gap-1.5 text-sm"
                  href="/product"
                >
                  Explore the product architecture
                  <ArrowRight aria-hidden="true" className="size-3.5" />
                </Link>
              </header>

              <div className="overflow-hidden rounded-xl border border-line bg-surface">
                <div className="grid border-b border-line bg-surface-subtle px-5 py-3 text-[0.6875rem] font-bold uppercase tracking-[0.1em] text-muted sm:grid-cols-[10rem_minmax(0,1fr)_9rem]">
                  <span>System layer</span>
                  <span className="hidden sm:block">Purpose</span>
                  <span className="hidden text-right sm:block">Control</span>
                </div>
                <ol className="divide-y divide-line">
                  {systemLayers.map(
                    ({ description, icon: Icon, label, meta }, index) => (
                      <li
                        className="grid gap-3 px-5 py-5 sm:grid-cols-[10rem_minmax(0,1fr)_9rem] sm:items-center"
                        key={label}
                      >
                        <div className="flex items-center gap-3">
                          <span className="grid size-8 shrink-0 place-items-center rounded-md border border-line bg-surface-subtle text-primary">
                            <Icon aria-hidden="true" className="size-4" />
                          </span>
                          <span className="text-sm font-semibold">{label}</span>
                        </div>
                        <p className="text-sm leading-6 text-muted">
                          {description}
                        </p>
                        <div className="flex items-center gap-2 text-xs font-semibold text-primary sm:justify-end">
                          <span>{meta}</span>
                          {index < systemLayers.length - 1 ? (
                            <ChevronRight
                              aria-hidden="true"
                              className="size-3.5 sm:rotate-90"
                            />
                          ) : (
                            <CheckCircle2
                              aria-hidden="true"
                              className="size-3.5"
                            />
                          )}
                        </div>
                      </li>
                    ),
                  )}
                </ol>
              </div>
            </div>
          </section>

          <section
            className="landing-section border-y border-line bg-surface"
            id="how-it-works"
          >
            <div className="site-container py-16 sm:py-24">
              <header className="grid gap-5 md:grid-cols-[1fr_1fr] md:items-end">
                <div>
                  <p className="eyebrow">Operating workflow</p>
                  <h2 className="balanced mt-3 max-w-2xl font-display text-3xl font-semibold tracking-[-0.04em] sm:text-4xl">
                    Move from raw history to approved work without losing
                    control.
                  </h2>
                </div>
                <p className="max-w-xl text-sm leading-7 text-muted md:justify-self-end">
                  Each stage has a clear input, review state, and next decision.
                  Uncertainty stays visible until you resolve it.
                </p>
              </header>

              <ol className="mt-12 grid border-l border-line md:grid-cols-4 md:border-l-0 md:border-t">
                {workflow.map(({ description, label }, index) => (
                  <li
                    className="relative px-6 py-6 md:min-h-52 md:px-6 md:pb-0 md:pt-9"
                    key={label}
                  >
                    <span className="absolute -left-[0.8rem] top-6 grid size-6 place-items-center rounded-full border border-line-strong bg-surface text-[0.6875rem] font-bold text-primary md:-top-3 md:left-6">
                      {index + 1}
                    </span>
                    <p className="text-[0.6875rem] font-bold uppercase tracking-[0.1em] text-muted">
                      Stage {index + 1}
                    </p>
                    <h3 className="mt-2 font-semibold text-foreground">
                      {label}
                    </h3>
                    <p className="mt-3 text-sm leading-6 text-muted">
                      {description}
                    </p>
                  </li>
                ))}
              </ol>
            </div>
          </section>

          <section className="landing-section site-container py-16 sm:py-24">
            <div className="rounded-2xl bg-navy px-6 py-8 text-white sm:px-10 sm:py-12 lg:px-14">
              <div className="grid gap-10 lg:grid-cols-[0.72fr_1.28fr] lg:gap-16">
                <header>
                  <p className="text-xs font-bold uppercase tracking-[0.12em] text-emerald-200/70">
                    From record to outcome
                  </p>
                  <h2 className="balanced mt-3 font-display text-3xl font-semibold tracking-[-0.04em] sm:text-4xl">
                    The resume is an output, not the database.
                  </h2>
                  <p className="mt-5 text-sm leading-7 text-emerald-50/65">
                    Reuse reviewed context across the work that surrounds an
                    opportunity without copying claims between disconnected
                    tools.
                  </p>
                </header>
                <div className="grid gap-px overflow-hidden rounded-xl border border-white/10 bg-white/10 sm:grid-cols-2">
                  {outputs.map(
                    ({ description, icon: CapabilityIcon, title }) => (
                      <div className="bg-navy px-5 py-5" key={title}>
                        <CapabilityIcon
                          aria-hidden="true"
                          className="size-5 text-emerald-300"
                        />
                        <h3 className="mt-4 text-sm font-semibold text-white">
                          {title}
                        </h3>
                        <p className="mt-1 text-xs leading-5 text-emerald-50/55">
                          {description}
                        </p>
                      </div>
                    ),
                  )}
                </div>
              </div>
            </div>
            <p className="mx-auto mt-5 max-w-3xl text-center text-xs leading-5 text-muted">
              Any readiness measurement shown in CareerOS is an internal,
              explainable aid. It is not an employer or
              applicant-tracking-system score, hiring probability, or guarantee.
            </p>
          </section>

          <section
            className="landing-section border-y border-line bg-surface"
            id="trust"
          >
            <div className="site-container grid gap-12 py-16 sm:py-24 lg:grid-cols-[0.78fr_1.22fr] lg:gap-16">
              <header>
                <div className="inline-flex size-10 items-center justify-center rounded-lg border border-primary/20 bg-primary-soft text-primary">
                  <ShieldCheck aria-hidden="true" className="size-5" />
                </div>
                <p className="eyebrow mt-5">Trust by construction</p>
                <h2 className="balanced mt-3 font-display text-3xl font-semibold tracking-[-0.04em] sm:text-4xl">
                  Product boundaries you can see, not promises you have to
                  infer.
                </h2>
                <p className="mt-5 text-sm leading-7 text-muted">
                  Examples in this preview are illustrative product states, not
                  a customer testimonial. Private data remains scoped to the
                  authorized user or tenant.
                </p>
                <Link
                  className="text-link mt-6 inline-flex items-center gap-1.5 text-sm"
                  href="/security"
                >
                  Review security and privacy
                  <ArrowRight aria-hidden="true" className="size-3.5" />
                </Link>
              </header>
              <div className="divide-y divide-line border-y border-line">
                {trustControls.map(
                  ({ description, icon: Icon, title }, index) => (
                    <div
                      className="grid gap-4 py-6 sm:grid-cols-[2rem_minmax(0,1fr)_auto] sm:items-start"
                      key={title}
                    >
                      <Icon
                        aria-hidden="true"
                        className="mt-0.5 size-5 text-primary"
                      />
                      <div>
                        <h3 className="font-semibold text-foreground">
                          {title}
                        </h3>
                        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
                          {description}
                        </p>
                      </div>
                      <span className="text-[0.6875rem] font-bold uppercase tracking-[0.1em] text-muted">
                        Control 0{index + 1}
                      </span>
                    </div>
                  ),
                )}
              </div>
            </div>
          </section>

          <section
            className="landing-section site-container py-16 sm:py-24"
            id="availability"
          >
            <div className="grid overflow-hidden rounded-xl border border-line bg-surface lg:grid-cols-[1fr_auto] lg:items-center">
              <div className="px-6 py-7 sm:px-8">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="warning">Technical preview</Badge>
                  <span className="text-xs font-semibold text-muted">
                    Commercial plans are not available
                  </span>
                </div>
                <h2 className="mt-4 font-display text-2xl font-semibold tracking-[-0.035em]">
                  Evaluate the product with fictional data.
                </h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
                  The current account flow supports hands-on technical
                  verification. Final pricing, entitlements, legal notices, and
                  support channels remain launch work.
                </p>
              </div>
              <div className="border-t border-line bg-surface-subtle px-6 py-6 lg:border-l lg:border-t-0 lg:px-8">
                <Link
                  className={cn(buttonStyles.base, buttonStyles.secondary)}
                  href="/pricing"
                >
                  View preview status
                  <ArrowRight aria-hidden="true" className="size-4" />
                </Link>
              </div>
            </div>
          </section>

          <section className="landing-section border-t border-line bg-surface">
            <div className="site-container grid gap-10 py-16 sm:py-24 lg:grid-cols-[0.6fr_1.4fr]">
              <header>
                <p className="eyebrow">Questions</p>
                <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.04em]">
                  Clear answers before you begin.
                </h2>
              </header>
              <div className="divide-y divide-line border-y border-line">
                {faqs.map(([question, answer]) => (
                  <details className="group py-5" key={question}>
                    <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-4 font-semibold text-foreground [&::-webkit-details-marker]:hidden">
                      {question}
                      <span
                        aria-hidden="true"
                        className="grid size-7 shrink-0 place-items-center rounded-full border border-line text-muted group-open:bg-surface-subtle"
                      >
                        <Check className="size-3.5" />
                      </span>
                    </summary>
                    <p className="max-w-3xl pb-1 pr-10 text-sm leading-7 text-muted">
                      {answer}
                    </p>
                  </details>
                ))}
              </div>
            </div>
          </section>

          <section className="landing-section border-t border-line bg-surface-subtle">
            <div className="site-container flex flex-col gap-7 py-14 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="flex items-center gap-2 text-primary">
                  <ShieldCheck aria-hidden="true" className="size-5" />
                  <span className="text-sm font-semibold">
                    Career truth before career polish
                  </span>
                </div>
                <h2 className="mt-3 max-w-2xl font-display text-2xl font-semibold tracking-[-0.035em] sm:text-3xl">
                  Build the record once. Keep every output accountable to it.
                </h2>
              </div>
              <Link
                className={cn(buttonStyles.base, buttonStyles.primary)}
                href="/demo/dashboard"
              >
                Explore the fictional demo
                <ArrowRight aria-hidden="true" className="size-4" />
              </Link>
            </div>
          </section>
        </main>
        <SiteFooter />
        <BackToTop />
      </div>
    </ProductMotionProvider>
  );
}
