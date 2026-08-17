import { ArrowRight, BadgeCheck, ShieldCheck, Sparkles } from "lucide-react";
import Link from "next/link";

import { Badge, buttonStyles, cn, SectionHeader } from "@rezumi/ui";

import {
  AttentionPanel,
  CareerRecordStats,
  PipelinePanel,
  QuickLaunch,
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
  attention: [],
  attentionDegraded: false,
  pipeline: UNAVAILABLE,
  record: {
    achievements: UNAVAILABLE,
    evidence: UNAVAILABLE,
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

function DashboardHero({
  displayName,
  nextStep,
}: {
  displayName: string;
  nextStep: NextStep;
}) {
  return (
    <section className="workspace-hero px-5 py-6 sm:px-8 sm:py-8">
      <div className="grid gap-7 lg:grid-cols-[minmax(0,1.15fr)_minmax(19rem,0.85fr)] lg:items-center">
        <div className="min-w-0">
          <p className="eyebrow">Workspace home</p>
          <h1 className="balanced mt-2 font-display text-[clamp(1.6rem,2.6vw,2.1rem)] font-semibold leading-[1.14] tracking-[-0.035em] text-foreground">
            Welcome to your Rezumi workspace, {displayName}.
          </h1>
          <p className="mt-3 max-w-xl text-sm leading-6 text-muted sm:text-[0.9375rem]">
            Start with the next useful action, then return to your structured
            career record whenever the underlying facts change.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Badge tone="success">
              <ShieldCheck aria-hidden="true" className="size-3.5" /> Private
              account
            </Badge>
            <Badge tone="primary">
              <BadgeCheck aria-hidden="true" className="size-3.5" /> Evidence
              grounded
            </Badge>
          </div>
        </div>

        <section
          aria-labelledby="next-step-heading"
          className="rounded-[var(--radius-card)] border border-primary/25 bg-surface/85 p-5 shadow-[var(--shadow-sm)] backdrop-blur-sm"
        >
          <p className="eyebrow flex items-center gap-1.5 !text-primary-strong">
            <Sparkles aria-hidden="true" className="size-3.5" />
            Next best step
          </p>
          <h2
            className="mt-2.5 text-lg font-semibold tracking-[-0.02em] text-foreground"
            id="next-step-heading"
          >
            {nextStep.title}
          </h2>
          <p className="mt-1.5 text-sm leading-6 text-muted">
            {nextStep.description}
          </p>
          <Link
            className={cn(
              buttonStyles.base,
              buttonStyles.primary,
              "mt-4 w-full",
            )}
            href={nextStep.href}
          >
            {nextStep.label}
            <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
          <p className="mt-3 text-xs leading-5 text-muted">
            You review factual changes before they become derived output.
          </p>
        </section>
      </div>
    </section>
  );
}

export function WorkspaceDashboard({
  displayName,
  onboardingComplete,
  resumeHealth = { kind: "empty" },
  summary = EMPTY_SUMMARY,
}: {
  displayName: string;
  onboardingComplete: boolean;
  resumeHealth?: DashboardResumeHealth;
  summary?: DashboardSummary;
}) {
  const nextStep = nextStepFor(onboardingComplete, resumeHealth, summary);

  return (
    <main className="workspace-page space-y-8" id="main-content">
      <DashboardHero displayName={displayName} nextStep={nextStep} />

      <CareerRecordStats record={summary.record} />

      <div className="grid gap-8 lg:grid-cols-2">
        <AttentionPanel
          degraded={summary.attentionDegraded}
          items={summary.attention}
        />
        <PipelinePanel pipeline={summary.pipeline} />
      </div>

      <section aria-labelledby="resume-state-heading">
        <SectionHeader
          actions={
            <Link className="text-link text-sm" href="/resume-health/account">
              Open Resume health
            </Link>
          }
          description="Only your latest persisted private-document state appears here."
          id="resume-state-heading"
          title="Latest resume state"
        />
        <div className="data-region">
          <ResumeState resumeHealth={resumeHealth} />
        </div>
      </section>

      <QuickLaunch />

      <TruthLockNote />
    </main>
  );
}
