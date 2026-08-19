import {
  ArrowRight,
  ArrowUpRight,
  BadgeCheck,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Badge, buttonStyles, cn } from "@rezumi/ui";

import { corpIdFor } from "@/shared/identity/corp-id";

import {
  ActivationChain,
  ActivationGate,
  activationChain,
  shouldGateWorkspace,
} from "../components/dashboard-activation";
import {
  AttentionPanel,
  CareerRecordStats,
  PipelinePanel,
  StandingTile,
  TruthLockNote,
} from "../components/dashboard-sections";
import {
  ResumeState,
  type DashboardResumeHealth,
} from "../components/dashboard-resume-state";
import type { DashboardSummary } from "../server/dashboard-summary";

export type { DashboardResumeHealth };

const UNAVAILABLE = { kind: "unavailable" } as const;

const EMPTY_SUMMARY: DashboardSummary = {
  activation: { jobs: UNAVAILABLE, pendingImports: UNAVAILABLE },
  attention: [],
  attentionDegraded: false,
  pipeline: UNAVAILABLE,
  record: {
    achievements: UNAVAILABLE,
    evidence: UNAVAILABLE,
    evidenceConfirmed: UNAVAILABLE,
    experiences: UNAVAILABLE,
    skills: UNAVAILABLE,
  },
};

type NextStep = {
  description: string;
  href: string;
  label: string;
  title: string;
};

function nextStepFor(
  onboardingComplete: boolean,
  resumeHealth: DashboardResumeHealth,
  summary: DashboardSummary,
): NextStep {
  if (!onboardingComplete) {
    return {
      description:
        "Your role and work preferences help Rezumi organize later recommendations without inventing career facts.",
      href: "/onboarding",
      label: "Continue setup",
      title: "Finish your account setup",
    };
  }
  if (resumeHealth.kind === "review") {
    return {
      description:
        "Confirm or correct the extracted fields before they become structured career data or analysis input.",
      href: `/resume-health/account/review/${encodeURIComponent(resumeHealth.documentId)}`,
      label: "Review parsed resume",
      title: "Check the parsed fields",
    };
  }
  if (
    resumeHealth.kind === "processing" ||
    resumeHealth.kind === "deleting" ||
    resumeHealth.kind === "failed" ||
    resumeHealth.kind === "error"
  ) {
    return {
      description:
        "Open Resume health for the latest server-backed status and any safe recovery action.",
      href: "/resume-health/account",
      label: "Open resume health",
      title: "Resolve the current resume state",
    };
  }
  const experiences = summary.record.experiences;
  if (experiences.kind === "count" && experiences.value === 0) {
    return {
      description:
        "Your career record is the source of truth behind every generated document. Add a role to give later outputs something eligible to cite.",
      href: "/career-profile",
      label: "Add your first role",
      title: "Start your career record",
    };
  }
  if (resumeHealth.kind === "report") {
    return {
      description:
        "Review the explainable findings, then choose which changes are worth considering. Nothing is changed automatically.",
      href: `/resume-health/account/report/${encodeURIComponent(resumeHealth.analysisId)}`,
      label: "Review findings",
      title: "Review your latest resume report",
    };
  }
  return {
    description:
      "A resume is optional, but adding one can accelerate your career record. You will review uncertain parsing before analysis.",
    href: "/resume-health/account",
    label: "Upload a resume",
    title: "Add a resume when you are ready",
  };
}

/**
 * Workspace masthead. The greeting and the one decision worth making sit on the
 * same line at the top of the page, so the fold carries identity and intent
 * rather than paragraphs of orientation copy.
 */
function DashboardHero({
  displayName,
  nextStep,
}: {
  displayName: string;
  nextStep: NextStep;
}) {
  return (
    <section className="workspace-hero px-5 py-6 sm:px-7 sm:py-8">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end lg:gap-10">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="success">
              <ShieldCheck aria-hidden="true" className="size-3.5" /> Private
            </Badge>
            <Badge tone="primary">
              <BadgeCheck aria-hidden="true" className="size-3.5" /> Evidence
              grounded
            </Badge>
          </div>
          <h1 className="balanced mt-3 font-display text-[clamp(1.6rem,3vw,2.4rem)] font-semibold leading-[1.08] tracking-[-0.04em] text-foreground">
            Welcome to your Rezumi workspace, {displayName}.
          </h1>
          <p className="balanced mt-2.5 max-w-xl text-sm leading-6 text-muted">
            One reviewed career record upstream. Everything below is derived
            from it, and nothing changes without your decision.
          </p>
        </div>

        <section
          aria-labelledby="next-step-heading"
          className="w-full min-w-0 rounded-[var(--radius-card)] border border-primary/25 bg-surface/85 p-4 shadow-[var(--shadow-sm)] backdrop-blur-sm lg:w-[22rem]"
        >
          <p className="metric-label flex items-center gap-1.5 !text-primary-strong">
            <Sparkles aria-hidden="true" className="size-3" />
            Next best step
          </p>
          <h2
            className="mt-1.5 font-display text-base font-semibold tracking-[-0.02em] text-foreground"
            id="next-step-heading"
          >
            {nextStep.title}
          </h2>
          <p className="mt-1 text-xs leading-5 text-muted">
            {nextStep.description}
          </p>
          <Link
            className={cn(
              buttonStyles.base,
              buttonStyles.primary,
              "mt-3.5 w-full justify-center",
            )}
            href={nextStep.href}
          >
            {nextStep.label}
            <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
        </section>
      </div>
    </section>
  );
}

export function WorkspaceDashboard({
  autoImport,
  displayName,
  onboardingComplete,
  resumeHealth = { kind: "empty" },
  summary = EMPTY_SUMMARY,
  userId,
}: {
  /**
   * Zero-touch import reporter, injected by the route so the workspace module
   * never depends on the Career Record module directly.
   */
  autoImport?: ReactNode;
  displayName: string;
  onboardingComplete: boolean;
  resumeHealth?: DashboardResumeHealth;
  summary?: DashboardSummary;
  /** Account identifier the Corp ID standing tile is derived from. */
  userId?: string;
}) {
  const corpId = userId === undefined ? null : corpIdFor(userId);
  if (onboardingComplete && shouldGateWorkspace(resumeHealth, summary)) {
    return <ActivationGate displayName={displayName} />;
  }

  const nextStep = nextStepFor(onboardingComplete, resumeHealth, summary);
  const chain = activationChain(resumeHealth, summary);
  const activating = chain.some(({ state }) => state !== "done");

  return (
    <main className="workspace-page space-y-5" id="main-content">
      <DashboardHero displayName={displayName} nextStep={nextStep} />

      {autoImport}

      {activating && <ActivationChain steps={chain} />}

      {/* Key figures first: the record is what everything else is derived from. */}
      <CareerRecordStats record={summary.record} />

      {/* Decisions on the left, the surfaces they come from on the right. */}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] xl:items-start">
        <AttentionPanel
          degraded={summary.attentionDegraded}
          items={summary.attention}
        />

        <div className="grid min-w-0 gap-4 sm:grid-cols-2 xl:grid-cols-1">
          <section
            aria-labelledby="resume-state-heading"
            className="dash-tile min-w-0"
          >
            <div className="flex items-center justify-between gap-3 px-4 pt-4 sm:px-5 sm:pt-5">
              <h2 className="metric-label" id="resume-state-heading">
                Latest resume state
              </h2>
              <Link
                className="inline-flex items-center gap-0.5 text-xs font-bold text-primary-strong hover:underline"
                href="/resume-health/account"
              >
                Open
                <ArrowUpRight aria-hidden="true" className="size-3.5" />
              </Link>
            </div>
            <ResumeState resumeHealth={resumeHealth} />
          </section>

          <PipelinePanel pipeline={summary.pipeline} />

          <StandingTile corpId={corpId} record={summary.record} />
        </div>
      </div>

      <TruthLockNote />
    </main>
  );
}
