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
 * Compact command bar. The old full-width hero spent most of the fold on
 * greeting copy; this keeps the identity line and moves the decision inline.
 */
function DashboardHero({
  displayName,
  nextStep,
}: {
  displayName: string;
  nextStep: NextStep;
}) {
  return (
    <section className="workspace-hero px-4 py-5 sm:px-6 sm:py-6">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between lg:gap-8">
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
          <h1 className="balanced mt-2.5 font-display text-[clamp(1.35rem,2.1vw,1.75rem)] font-semibold leading-[1.15] tracking-[-0.035em] text-foreground">
            Welcome to your Rezumi workspace, {displayName}.
          </h1>
        </div>

        <section
          aria-labelledby="next-step-heading"
          className="flex shrink-0 flex-col gap-3 rounded-[var(--radius-card)] border border-primary/25 bg-surface/80 p-4 backdrop-blur-sm sm:flex-row sm:items-center lg:max-w-xl"
        >
          <span className="grid size-9 shrink-0 place-items-center rounded-[var(--radius-small)] bg-primary text-white">
            <Sparkles aria-hidden="true" className="size-4" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="metric-label !text-primary-strong">Next best step</p>
            <h2
              className="mt-0.5 text-sm font-semibold text-foreground"
              id="next-step-heading"
            >
              {nextStep.title}
            </h2>
            <p className="mt-0.5 text-xs leading-5 text-muted">
              {nextStep.description}
            </p>
          </div>
          <Link
            className={cn(
              buttonStyles.base,
              buttonStyles.primary,
              "shrink-0 self-start sm:self-center",
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
    <main className="workspace-page space-y-4" id="main-content">
      <DashboardHero displayName={displayName} nextStep={nextStep} />

      {autoImport}

      {activating && <ActivationChain steps={chain} />}

      {/* Bento row: the hero metric, the record, and standing. */}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,5fr)_minmax(0,4fr)_minmax(0,3fr)]">
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

        <CareerRecordStats record={summary.record} />

        <StandingTile corpId={corpId} record={summary.record} />
      </div>

      {/* Bento row: what needs a decision, and where opportunities stand. */}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)]">
        <AttentionPanel
          degraded={summary.attentionDegraded}
          items={summary.attention}
        />
        <PipelinePanel pipeline={summary.pipeline} />
      </div>

      <TruthLockNote />
    </main>
  );
}
