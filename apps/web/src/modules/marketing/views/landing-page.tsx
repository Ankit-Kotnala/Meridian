import {
  ArrowRight,
  Check,
  FileCheck2,
  GitBranch,
  LockKeyhole,
  MessageSquareText,
  SearchCheck,
  ShieldCheck,
  UserRoundCheck,
} from "lucide-react";
import Link from "next/link";

import { Badge, buttonStyles, cn } from "@careeros/ui";

import { SiteFooter } from "@/shared/components/public-site-footer";
import { SiteHeader } from "@/shared/components/public-site-header";

const operatingModel = [
  {
    description: "Roles, projects, skills, achievements, and preferences.",
    icon: UserRoundCheck,
    label: "Structured career facts",
  },
  {
    description: "Eligible sources and your explicit confirmation.",
    icon: GitBranch,
    label: "Evidence and provenance",
  },
  {
    description: "Resumes, answers, stories, and messages you approve.",
    icon: FileCheck2,
    label: "Controlled outputs",
  },
] as const;

const capabilityRows = [
  [
    "Maintain career truth",
    "Keep experience, achievements, skills, and evidence in one durable record instead of copying facts between documents.",
  ],
  [
    "Understand the requirement",
    "Separate general resume health, role readiness, and exact job coverage so each measure answers one clear question.",
  ],
  [
    "Create with control",
    "See the original, proposed change, reason, evidence, and relevant requirement before accepting material edits.",
  ],
  [
    "Carry context forward",
    "Use the same reviewed record for applications, interview stories, networking, and long-term growth.",
  ],
] as const;

const workflow = [
  {
    description:
      "Start manually or import a resume. Uncertain parsing is held for review.",
    label: "Build the record",
  },
  {
    description:
      "Attach eligible sources, capture achievements, and confirm what is true.",
    label: "Connect evidence",
  },
  {
    description:
      "Explore roles or bring a specific job description into a protected workflow.",
    label: "Choose the context",
  },
  {
    description:
      "Compare, edit, accept, or reject every material document change before export.",
    label: "Review the output",
  },
] as const;

const trustRows = [
  {
    description:
      "Missing facts produce a question, not polished prose that looks factual.",
    icon: MessageSquareText,
    title: "No made-up achievements",
  },
  {
    description:
      "Generated factual claims retain machine-checkable links to eligible evidence.",
    icon: SearchCheck,
    title: "Provenance stays visible",
  },
  {
    description:
      "Private uploads are validated and processed through constrained, ownership-aware paths.",
    icon: LockKeyhole,
    title: "Sensitive data stays scoped",
  },
] as const;

const faqs = [
  [
    "Does CareerOS know an employer’s ATS score?",
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

export function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />
      <main id="main-content">
        <section className="border-b border-line bg-white">
          <div className="site-container grid gap-12 py-16 sm:py-20 lg:grid-cols-[minmax(0,1.1fr)_minmax(22rem,0.9fr)] lg:items-center lg:py-28">
            <div>
              <Badge tone="neutral">Technical product preview</Badge>
              <h1 className="balanced mt-6 max-w-4xl font-display text-4xl font-semibold leading-[1.08] tracking-[-0.045em] text-foreground sm:text-5xl lg:text-[4.25rem]">
                Your career story, built on evidence.
              </h1>
              <p className="mt-6 max-w-2xl text-lg leading-8 text-muted">
                CareerOS keeps the facts of your career upstream, connects them
                to supporting evidence, and helps you create application work
                you can inspect and control.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link
                  className={cn(buttonStyles.base, buttonStyles.primary)}
                  href="/register"
                >
                  Create a preview account
                  <ArrowRight aria-hidden="true" className="size-4" />
                </Link>
                <Link
                  className={cn(buttonStyles.base, buttonStyles.secondary)}
                  href="/demo/dashboard"
                >
                  Explore the fictional demo
                </Link>
              </div>
              <p className="mt-4 text-xs leading-5 text-muted">
                Use fictional or non-sensitive content during technical preview
                testing. Production legal notices are not complete.
              </p>
            </div>

            <aside
              aria-labelledby="operating-model-title"
              className="border-l-2 border-primary bg-surface-raised px-5 py-2 sm:px-7"
            >
              <p className="eyebrow">The operating model</p>
              <h2
                className="mt-2 text-xl font-semibold tracking-[-0.025em]"
                id="operating-model-title"
              >
                One reviewed record. Many useful outputs.
              </h2>
              <ol className="mt-7">
                {operatingModel.map(
                  ({ description, icon: Icon, label }, index) => (
                    <li
                      className="relative grid grid-cols-[2.25rem_minmax(0,1fr)] gap-3 pb-6 last:pb-0"
                      key={label}
                    >
                      {index < operatingModel.length - 1 && (
                        <span
                          aria-hidden="true"
                          className="absolute bottom-0 left-[1.0625rem] top-8 w-px bg-line-strong"
                        />
                      )}
                      <span className="grid size-9 place-items-center rounded-full border border-line-strong bg-white text-primary">
                        <Icon aria-hidden="true" className="size-4" />
                      </span>
                      <span>
                        <span className="block text-sm font-semibold">
                          {label}
                        </span>
                        <span className="mt-1 block text-sm leading-6 text-muted">
                          {description}
                        </span>
                      </span>
                    </li>
                  ),
                )}
              </ol>
            </aside>
          </div>
        </section>

        <section className="site-container py-16 sm:py-24" id="product">
          <div className="grid gap-10 lg:grid-cols-[0.75fr_1.25fr]">
            <header>
              <p className="eyebrow">A career operating system</p>
              <h2 className="balanced mt-3 font-display text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">
                Stop rebuilding your history for every opportunity.
              </h2>
              <p className="mt-4 text-sm leading-7 text-muted">
                A resume is one output. CareerOS treats your structured career
                record and evidence graph as the durable source behind it.
              </p>
              <Link
                className="text-link mt-5 inline-flex text-sm"
                href="/product"
              >
                Read the product overview
              </Link>
            </header>
            <dl className="divide-y divide-line border-y border-line">
              {capabilityRows.map(([title, description]) => (
                <div
                  className="grid gap-2 py-5 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-7"
                  key={title}
                >
                  <dt className="font-semibold text-foreground">{title}</dt>
                  <dd className="text-sm leading-6 text-muted">
                    {description}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        <section className="border-y border-line bg-white" id="how-it-works">
          <div className="site-container py-16 sm:py-24">
            <header className="max-w-2xl">
              <p className="eyebrow">How it works</p>
              <h2 className="balanced mt-3 font-display text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">
                Progress without surrendering control.
              </h2>
            </header>
            <ol className="mt-10 grid border-l border-line md:grid-cols-4 md:border-l-0 md:border-t">
              {workflow.map(({ description, label }, index) => (
                <li className="relative px-5 py-6 md:px-6 md:pt-8" key={label}>
                  <span className="absolute -left-[0.8rem] top-6 grid size-6 place-items-center rounded-full border border-line-strong bg-white text-[0.6875rem] font-bold text-muted md:-top-3 md:left-6">
                    {index + 1}
                  </span>
                  <h3 className="font-semibold text-foreground">{label}</h3>
                  <p className="mt-2 text-sm leading-6 text-muted">
                    {description}
                  </p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="site-container py-16 sm:py-24" id="trust">
          <div className="grid gap-10 lg:grid-cols-[0.8fr_1.2fr]">
            <header>
              <p className="eyebrow">Trust by construction</p>
              <h2 className="balanced mt-3 font-display text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">
                Better career work starts with honest boundaries.
              </h2>
              <p className="mt-4 text-sm leading-7 text-muted">
                Examples in this preview are illustrative product states, not a
                customer testimonial. Readiness measures do not guarantee
                outcomes.
              </p>
            </header>
            <div className="divide-y divide-line border-y border-line">
              {trustRows.map(({ description, icon: Icon, title }) => (
                <div className="flex gap-4 py-5" key={title}>
                  <Icon
                    aria-hidden="true"
                    className="mt-0.5 size-5 shrink-0 text-primary"
                  />
                  <div>
                    <h3 className="font-semibold text-foreground">{title}</h3>
                    <p className="mt-1 text-sm leading-6 text-muted">
                      {description}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section
          className="border-y border-line bg-navy text-white"
          id="availability"
        >
          <div className="site-container grid gap-8 py-14 md:grid-cols-[1fr_auto] md:items-center">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.1em] text-emerald-100/60">
                Preview availability
              </p>
              <h2 className="mt-3 font-display text-2xl font-semibold tracking-[-0.03em] sm:text-3xl">
                Commercial plans are not available yet.
              </h2>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-emerald-50/70">
                Final prices and entitlements will come from launch
                configuration. The current account flow exists for technical
                verification with fictional or non-sensitive content.
              </p>
            </div>
            <Link
              className={cn(
                buttonStyles.base,
                "bg-white text-navy hover:bg-surface-subtle",
              )}
              href="/pricing"
            >
              View preview status
              <ArrowRight aria-hidden="true" className="size-4" />
            </Link>
          </div>
        </section>

        <section className="site-container grid gap-10 py-16 sm:py-24 lg:grid-cols-[0.65fr_1.35fr]">
          <header>
            <p className="eyebrow">Questions</p>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.035em]">
              Clear answers before you begin.
            </h2>
          </header>
          <div className="divide-y divide-line border-y border-line">
            {faqs.map(([question, answer]) => (
              <details className="group py-5" key={question}>
                <summary className="flex min-h-11 list-none items-center justify-between gap-4 font-semibold text-foreground [&::-webkit-details-marker]:hidden">
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
        </section>

        <section className="border-t border-line bg-white">
          <div className="site-container flex flex-col gap-6 py-14 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2 text-primary">
                <ShieldCheck aria-hidden="true" className="size-5" />
                <span className="text-sm font-semibold">Evidence first</span>
              </div>
              <h2 className="mt-3 max-w-2xl font-display text-2xl font-semibold tracking-[-0.03em] sm:text-3xl">
                Build the record before polishing the story.
              </h2>
            </div>
            <Link
              className={cn(buttonStyles.base, buttonStyles.primary)}
              href="/get-started"
            >
              Choose how to start
              <ArrowRight aria-hidden="true" className="size-4" />
            </Link>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
