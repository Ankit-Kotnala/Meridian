import {
  Activity,
  Archive,
  ArrowRight,
  BadgeCheck,
  BriefcaseBusiness,
  Check,
  FileCheck2,
  FileSearch,
  LockKeyhole,
  MessageSquareText,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Target,
  Upload,
  UserRoundCheck,
  WandSparkles,
  Workflow,
} from "lucide-react";
import Link from "next/link";
import type { ComponentType, SVGProps } from "react";

import { Badge, buttonStyles, cn } from "@careeros/ui";

import { ProductPreview } from "@/modules/marketing/components/product-preview";
import { SiteFooter } from "@/modules/marketing/components/site-footer";
import { SiteHeader } from "@/modules/marketing/components/site-header";

type Icon = ComponentType<SVGProps<SVGSVGElement>>;

const principles: Array<{ icon: Icon; title: string; description: string }> = [
  {
    icon: ShieldCheck,
    title: "Truth-locked by design",
    description:
      "Suggested claims must trace back to career evidence you control. Missing facts become questions—not guesses.",
  },
  {
    icon: Archive,
    title: "One career source of truth",
    description:
      "Keep experience, achievements, skills, and proof in a durable profile instead of rebuilding every application.",
  },
  {
    icon: UserRoundCheck,
    title: "You approve every change",
    description:
      "Review the original, rationale, requirement, and supporting evidence before accepting or editing material changes.",
  },
];

const workflow = [
  {
    number: "01",
    icon: Upload,
    title: "Bring your career history",
    description:
      "Start with a resume, then correct uncertain fields and grow a structured profile over time.",
  },
  {
    number: "02",
    icon: ScanSearch,
    title: "Understand readiness",
    description:
      "See general resume health, role readiness, or exact job requirement coverage—with plain-language explanations.",
  },
  {
    number: "03",
    icon: WandSparkles,
    title: "Create with evidence",
    description:
      "Review grounded changes and generate consistent resumes, application answers, and interview stories.",
  },
  {
    number: "04",
    icon: Activity,
    title: "Learn from the search",
    description:
      "Track applications and outcomes as patterns, never as promises or proof of causation.",
  },
];

const capabilities: Array<{
  icon: Icon;
  eyebrow: string;
  title: string;
  description: string;
  bullets: string[];
  accent: string;
}> = [
  {
    icon: FileSearch,
    eyebrow: "General resume health",
    title:
      "See what your resume communicates before a job description enters the picture.",
    description:
      "CareerOS evaluates machine readability, recruiter clarity, content impact, structure, consistency, and evidence confidence using internal, explainable readiness measures.",
    bullets: [
      "Parsing and reading-order previews",
      "Prioritized issues and quick wins",
      "No claim of an employer’s ATS score",
    ],
    accent: "bg-primary-soft text-primary",
  },
  {
    icon: Archive,
    eyebrow: "Career Evidence Vault",
    title:
      "Turn scattered career facts into a profile you can trust and reuse.",
    description:
      "Connect achievements, projects, metrics, files, and confirmations to the experience and skills they support. Every output keeps its provenance.",
    bullets: [
      "Verification and confirmation states",
      "Source spans and attachment links",
      "Unsupported evidence stays out of generated content",
    ],
    accent: "bg-success-soft text-success",
  },
  {
    icon: Target,
    eyebrow: "Roles and exact jobs",
    title:
      "Separate broad career readiness from the requirements of one opportunity.",
    description:
      "Explore target roles without a posting, then import an exact job when you are ready. CareerOS shows strengths, transferable evidence, unknowns, and hard gaps separately.",
    bullets: [
      "Requirement-to-evidence mapping",
      "Role transition guidance",
      "Mandatory gaps remain visible",
    ],
    accent: "bg-warning-soft text-warning",
  },
  {
    icon: Workflow,
    eyebrow: "Change Studio",
    title:
      "A review queue for meaningful edits—not an autopilot rewrite button.",
    description:
      "Compare original and suggested language, inspect the reason and supporting evidence, then accept, reject, edit, regenerate, or undo each operation.",
    bullets: [
      "Evidence-backed rationale",
      "Human approval on material changes",
      "Version history and restoration",
    ],
    accent: "bg-primary-soft text-primary",
  },
];

const ecosystem = [
  {
    icon: FileCheck2,
    title: "Verified exports",
    description:
      "Generate readable PDF and DOCX files, then parse them again to catch broken reading order or missing content.",
  },
  {
    icon: BriefcaseBusiness,
    title: "Application workspace",
    description:
      "Keep jobs, deadlines, tasks, documents, contacts, interviews, and exact resume versions together.",
  },
  {
    icon: MessageSquareText,
    title: "Interview readiness",
    description:
      "Connect important resume claims to defensible STAR stories and identify where stronger evidence is still needed.",
  },
];

const trustItems: Array<{ icon: Icon; title: string; description: string }> = [
  {
    icon: LockKeyhole,
    title: "Private by default",
    description:
      "User content is not intended for model training by default, and raw resumes stay out of analytics and logs.",
  },
  {
    icon: ShieldCheck,
    title: "Evidence before claims",
    description:
      "A grounding layer blocks unsupported career statements from accepted generated content.",
  },
  {
    icon: ScanSearch,
    title: "Explainable scores",
    description:
      "Deterministic, versioned formulas expose components and weights instead of asking an LLM for a final score.",
  },
  {
    icon: UserRoundCheck,
    title: "Meaningful control",
    description:
      "People can inspect, edit, reject, undo, restore, export, and delete their own career data.",
  },
];

const plans: ReadonlyArray<{
  name: string;
  summary: string;
  features: readonly string[];
  featured: boolean;
}> = [
  {
    name: "Free",
    summary: "Start your source of truth.",
    features: [
      "One career profile",
      "Limited readiness checks",
      "Report preview",
      "One verified export",
    ],
    featured: false,
  },
  {
    name: "Job Hunt Sprint",
    summary: "Focused tools for an active search.",
    features: [
      "Exact job matching",
      "Change Studio",
      "Application packs",
      "Multiple verified exports",
    ],
    featured: true,
  },
  {
    name: "Pro",
    summary: "Continuous career operations.",
    features: [
      "Full role exploration",
      "Application workspace",
      "Interview preparation",
      "Achievement capture and analytics",
    ],
    featured: false,
  },
];

const faqs = [
  {
    question: "Does CareerOS know my employer’s ATS score?",
    answer:
      "No. CareerOS reports internal readiness measurements such as Resume Health, Machine Readability, and Requirement Coverage. They are not provided by an employer or applicant tracking system.",
  },
  {
    question: "Will AI add impressive details that are missing?",
    answer:
      "No. Missing dates, metrics, ownership, team size, or outcomes should produce a question for you. Generated career claims must connect to supported evidence.",
  },
  {
    question: "Can CareerOS guarantee interviews?",
    answer:
      "No. Hiring decisions involve many factors outside any application tool. CareerOS helps you improve clarity, evidence, consistency, and workflow without promising employment outcomes.",
  },
  {
    question: "Is the dashboard on this site real user data?",
    answer:
      "No. The public demo dashboard is made entirely from fictional fixtures and remains separate from protected accounts. Signed-in Resume Health workspaces and short-lived guest checks use their own persisted document state.",
  },
];

export function LandingPage() {
  return (
    <div className="overflow-x-hidden bg-white">
      <SiteHeader />
      <main id="main-content">
        <section className="relative overflow-hidden border-b border-line bg-[linear-gradient(180deg,#fff_0%,#f7f5ff_100%)] py-16 sm:py-20 lg:py-24">
          <div
            aria-hidden="true"
            className="absolute left-[8%] top-24 size-64 rounded-full bg-violet-200/30 blur-3xl"
          />
          <div className="site-container relative grid items-center gap-14 lg:grid-cols-[0.95fr_1.05fr] lg:gap-10">
            <div>
              <Badge className="mb-6" tone="primary">
                <Sparkles aria-hidden="true" className="size-3" /> A career
                application operating system
              </Badge>
              <h1 className="balanced max-w-3xl text-4xl font-black tracking-[-0.045em] text-foreground sm:text-5xl lg:text-[4rem] lg:leading-[1.04]">
                Your career story, built on{" "}
                <span className="text-primary">evidence.</span>
              </h1>
              <p className="mt-6 max-w-xl text-base leading-7 text-muted sm:text-lg sm:leading-8">
                Build one verified career profile. Understand your readiness.
                Tailor every application without inventing a single fact.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link
                  className={cn(
                    buttonStyles.base,
                    buttonStyles.primary,
                    "min-h-12 px-5",
                  )}
                  href="/demo/dashboard"
                >
                  Explore the fictional demo
                  <ArrowRight aria-hidden="true" className="size-4" />
                </Link>
                <Link
                  className={cn(
                    buttonStyles.base,
                    buttonStyles.secondary,
                    "min-h-12 px-5",
                  )}
                  href="/resume-health"
                >
                  See how Resume Health works
                </Link>
              </div>
              <ul className="mt-8 grid gap-3 text-sm font-semibold text-foreground sm:grid-cols-2">
                {[
                  "No made-up achievements",
                  "No black-box hiring promises",
                  "You approve every material edit",
                  "Privacy-first by default",
                ].map((item) => (
                  <li className="flex items-center gap-2" key={item}>
                    <span className="grid size-5 place-items-center rounded-full bg-success-soft text-success">
                      <Check
                        aria-hidden="true"
                        className="size-3"
                        strokeWidth={3}
                      />
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            <ProductPreview />
          </div>
        </section>

        <section className="py-20 sm:py-24" id="product">
          <div className="site-container">
            <div className="mx-auto max-w-2xl text-center">
              <p className="eyebrow">A better foundation</p>
              <h2 className="balanced mt-3 text-3xl font-black tracking-[-0.035em] text-foreground sm:text-4xl">
                Your resume is an output. Your verified career profile is the
                source.
              </h2>
              <p className="mt-5 text-base leading-7 text-muted">
                Stop rebuilding the facts of your career for every application.
                CareerOS organizes the evidence once, then helps you use it
                consistently.
              </p>
            </div>
            <div className="mt-12 grid gap-5 md:grid-cols-3">
              {principles.map(({ icon: IconComponent, title, description }) => (
                <article
                  className="rounded-2xl border border-line bg-white p-6 shadow-[0_12px_36px_rgba(20,30,72,.06)]"
                  key={title}
                >
                  <span className="grid size-11 place-items-center rounded-xl bg-primary-soft text-primary">
                    <IconComponent aria-hidden="true" className="size-5" />
                  </span>
                  <h3 className="mt-5 text-lg font-extrabold tracking-[-0.02em]">
                    {title}
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-muted">
                    {description}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="border-y border-line bg-background py-20 sm:py-24">
          <div className="site-container space-y-16 lg:space-y-24">
            {capabilities.map(
              (
                {
                  icon: IconComponent,
                  eyebrow,
                  title,
                  description,
                  bullets,
                  accent,
                },
                index,
              ) => (
                <article
                  className="grid items-center gap-9 lg:grid-cols-2 lg:gap-16"
                  key={title}
                >
                  <div className={cn(index % 2 === 1 && "lg:order-2")}>
                    <p className="eyebrow">{eyebrow}</p>
                    <h2 className="balanced mt-3 text-3xl font-black tracking-[-0.035em] text-foreground">
                      {title}
                    </h2>
                    <p className="mt-5 leading-7 text-muted">{description}</p>
                    <ul className="mt-6 space-y-3 text-sm font-semibold text-foreground">
                      {bullets.map((bullet) => (
                        <li className="flex items-start gap-2.5" key={bullet}>
                          <BadgeCheck
                            aria-hidden="true"
                            className="mt-0.5 size-4 shrink-0 text-success"
                          />{" "}
                          {bullet}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div
                    className={cn(
                      "rounded-[1.75rem] border border-line bg-white p-5 shadow-[0_18px_60px_rgba(20,30,72,.08)] sm:p-8",
                      index % 2 === 1 && "lg:order-1",
                    )}
                  >
                    <div
                      className={cn(
                        "grid size-12 place-items-center rounded-2xl",
                        accent,
                      )}
                    >
                      <IconComponent aria-hidden="true" className="size-6" />
                    </div>
                    <div className="mt-7 space-y-3">
                      {bullets.map((bullet, bulletIndex) => (
                        <div
                          className="flex items-center justify-between gap-4 rounded-xl border border-line bg-slate-50/70 p-4"
                          key={bullet}
                        >
                          <div className="flex items-center gap-3">
                            <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-white text-xs font-black text-primary shadow-sm">
                              {bulletIndex + 1}
                            </span>
                            <span className="text-sm font-bold text-foreground">
                              {bullet}
                            </span>
                          </div>
                          <Check
                            aria-hidden="true"
                            className="size-4 shrink-0 text-success"
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                </article>
              ),
            )}
          </div>
        </section>

        <section className="py-20 sm:py-24" id="how-it-works">
          <div className="site-container">
            <div className="max-w-2xl">
              <p className="eyebrow">How it works</p>
              <h2 className="balanced mt-3 text-3xl font-black tracking-[-0.035em] sm:text-4xl">
                One connected workflow, from career history to interview room.
              </h2>
            </div>
            <ol className="mt-12 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
              {workflow.map(
                ({ number, icon: IconComponent, title, description }) => (
                  <li
                    className="relative rounded-2xl border border-line bg-white p-6"
                    key={number}
                  >
                    <span className="absolute right-5 top-4 text-4xl font-black tracking-[-0.06em] text-slate-100">
                      {number}
                    </span>
                    <span className="grid size-10 place-items-center rounded-xl bg-primary-soft text-primary">
                      <IconComponent aria-hidden="true" className="size-5" />
                    </span>
                    <h3 className="mt-5 font-extrabold">{title}</h3>
                    <p className="mt-2 text-sm leading-6 text-muted">
                      {description}
                    </p>
                  </li>
                ),
              )}
            </ol>
            <div className="mt-8 grid gap-5 md:grid-cols-3">
              {ecosystem.map(({ icon: IconComponent, title, description }) => (
                <article
                  className="rounded-2xl bg-navy p-6 text-white"
                  key={title}
                >
                  <IconComponent
                    aria-hidden="true"
                    className="size-5 text-violet-300"
                  />
                  <h3 className="mt-5 font-extrabold">{title}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-300">
                    {description}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section
          className="border-y border-line bg-[#f6f8fc] py-20 sm:py-24"
          id="trust"
        >
          <div className="site-container grid items-start gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:gap-16">
            <div>
              <p className="eyebrow">Trust is a product feature</p>
              <h2 className="balanced mt-3 text-3xl font-black tracking-[-0.035em] sm:text-4xl">
                Designed for sensitive career data and honest output.
              </h2>
              <p className="mt-5 leading-7 text-muted">
                CareerOS is being built around least-data AI requests, redacted
                logs, configurable retention, clear consent, evidence
                traceability, and user-controlled deletion.
              </p>
              <Link
                className={cn(
                  buttonStyles.base,
                  buttonStyles.secondary,
                  "mt-7",
                )}
                href="/security"
              >
                Read the security approach{" "}
                <ArrowRight aria-hidden="true" className="size-4" />
              </Link>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {trustItems.map(({ icon: IconComponent, title, description }) => (
                <article
                  className="rounded-2xl border border-line bg-white p-5 shadow-sm"
                  key={title}
                >
                  <IconComponent
                    aria-hidden="true"
                    className="size-5 text-primary"
                  />
                  <h3 className="mt-4 font-extrabold">{title}</h3>
                  <p className="mt-2 text-sm leading-6 text-muted">
                    {description}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="py-20 sm:py-24">
          <div className="site-container">
            <div className="mx-auto max-w-3xl rounded-[1.75rem] border border-dashed border-primary/35 bg-primary-soft/45 p-8 text-center sm:p-11">
              <Badge tone="primary">
                Illustrative scenario · not a customer testimonial
              </Badge>
              <p className="balanced mt-6 text-xl font-extrabold leading-8 tracking-[-0.02em] text-foreground sm:text-2xl">
                “I can see which claims have evidence, which role gaps are real,
                and what I still need to answer before I send an application.”
              </p>
              <p className="mt-4 text-sm text-muted">
                Fictional product-use scenario for this public demo.
              </p>
            </div>
          </div>
        </section>

        <section
          className="border-y border-line bg-background py-20 sm:py-24"
          id="pricing"
        >
          <div className="site-container">
            <div className="mx-auto max-w-2xl text-center">
              <p className="eyebrow">Plans that match the moment</p>
              <h2 className="balanced mt-3 text-3xl font-black tracking-[-0.035em] sm:text-4xl">
                Start small. Add depth when your search needs it.
              </h2>
              <p className="mt-4 leading-7 text-muted">
                Prices and exact entitlements will be loaded from product
                configuration before launch—not duplicated in the interface.
              </p>
            </div>
            <div className="mt-12 grid gap-5 lg:grid-cols-3">
              {plans.map((plan) => (
                <article
                  className={cn(
                    "relative rounded-2xl border bg-white p-6",
                    plan.featured
                      ? "border-primary shadow-[0_18px_50px_rgba(91,70,245,.14)]"
                      : "border-line",
                  )}
                  key={plan.name}
                >
                  {plan.featured && (
                    <Badge className="absolute right-5 top-5" tone="primary">
                      Active-search favorite
                    </Badge>
                  )}
                  <h3 className="text-xl font-black tracking-[-0.03em]">
                    {plan.name}
                  </h3>
                  <p className="mt-2 text-sm text-muted">{plan.summary}</p>
                  <p className="mt-7 text-2xl font-black tracking-tight">
                    Pricing at launch
                  </p>
                  <ul className="mt-6 space-y-3 border-t border-line pt-6 text-sm">
                    {plan.features.map((feature) => (
                      <li className="flex items-start gap-2.5" key={feature}>
                        <Check
                          aria-hidden="true"
                          className="mt-0.5 size-4 shrink-0 text-success"
                        />
                        <span>{feature}</span>
                      </li>
                    ))}
                  </ul>
                  <Link
                    className={cn(
                      buttonStyles.base,
                      plan.featured
                        ? buttonStyles.primary
                        : buttonStyles.secondary,
                      "mt-7 w-full",
                    )}
                    href="/register"
                  >
                    Join the product preview
                  </Link>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="py-20 sm:py-24">
          <div className="site-container grid gap-10 lg:grid-cols-[0.7fr_1.3fr] lg:gap-16">
            <div>
              <p className="eyebrow">Questions, answered</p>
              <h2 className="balanced mt-3 text-3xl font-black tracking-[-0.035em]">
                Clear limits build a more useful product.
              </h2>
            </div>
            <div className="divide-y divide-line rounded-2xl border border-line bg-white px-5 sm:px-7">
              {faqs.map((faq) => (
                <details className="group py-5" key={faq.question}>
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-extrabold text-foreground marker:hidden">
                    {faq.question}
                    <span
                      aria-hidden="true"
                      className="text-xl font-normal text-primary transition group-open:rotate-45"
                    >
                      +
                    </span>
                  </summary>
                  <p className="max-w-2xl pt-3 text-sm leading-6 text-muted">
                    {faq.answer}
                  </p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="bg-[linear-gradient(135deg,#0b1d42_0%,#17134d_56%,#3d2bb8_100%)] py-20 text-white">
          <div className="site-container text-center">
            <Sparkles
              aria-hidden="true"
              className="mx-auto size-7 text-violet-300"
            />
            <h2 className="balanced mx-auto mt-5 max-w-3xl text-3xl font-black tracking-[-0.04em] sm:text-4xl">
              Build an application system that remembers the truth.
            </h2>
            <p className="mx-auto mt-5 max-w-xl leading-7 text-slate-300">
              Run a short-lived guest Resume Health check, or sign in to keep
              reviewed documents and reports in your protected workspace.
            </p>
            <Link
              className={cn(
                buttonStyles.base,
                "mt-8 min-h-12 bg-white px-6 text-navy hover:bg-violet-50",
              )}
              href="/resume-health/guest"
            >
              Check my resume{" "}
              <ArrowRight aria-hidden="true" className="size-4" />
            </Link>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
