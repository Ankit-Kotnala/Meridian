import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  FileText,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { buttonStyles, cn, ScoreRing } from "@rezumi/ui";

import { corpIdFor } from "@/shared/identity/corp-id";

import { DashboardActivity } from "../components/dashboard-activity";
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
  ResumeHelpBanner,
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

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

function firstName(displayName: string): string {
  return displayName.trim().split(/\s+/)[0] ?? displayName;
}

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
  if (resumeHealth.kind === "importReady") {
    return {
      description:
        "Your reviewed resume facts are being added to your career record automatically. Open your profile to see experiences, skills, and contact details.",
      href: "/career-profile",
      label: "Open career profile",
      title: "Populate your career record",
    };
  }
  const experiences = summary.record.experiences;
  if (
    resumeHealth.kind === "report" &&
    experiences.kind === "count" &&
    experiences.value === 0
  ) {
    return {
      description:
        "Parsed resume facts should appear in your career record automatically after upload. Refresh this page or open your profile if they have not landed yet.",
      href: "/career-profile",
      label: "Open career profile",
      title: "Add parsed resume facts to your record",
    };
  }
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

function HeroIllustration() {
  return (
    <div
      aria-hidden="true"
      className="preview-float relative mx-auto w-full max-w-[15rem] lg:absolute lg:right-8 lg:top-1/2 lg:mx-0 lg:-translate-y-1/2"
    >
      <div className="absolute inset-0 rounded-full bg-white/50 blur-2xl" />
      <div className="relative rounded-2xl border border-white/80 bg-white/95 p-4 shadow-[0_12px_32px_-16px_rgb(10_41_26_/_0.2)]">
        <div className="flex items-center gap-2">
          <FileText className="size-5 text-primary" strokeWidth={1.75} />
          <span className="text-xs font-semibold text-primary">Resume</span>
        </div>
        <div className="mt-3 space-y-2">
          <div className="h-1.5 w-full rounded-full bg-primary-soft" />
          <div className="h-1.5 w-4/5 rounded-full bg-primary-soft" />
          <div className="h-1.5 w-3/5 rounded-full bg-primary-soft" />
        </div>
        <CheckCircle2
          className="absolute -right-2 -top-2 size-8 text-success"
          strokeWidth={2}
        />
      </div>
      <span className="absolute -left-3 top-5 rounded-[var(--radius-pill)] border border-white/80 bg-white px-2.5 py-1 text-[0.625rem] font-semibold text-primary">
        Better Resume
      </span>
      <span className="absolute -right-2 bottom-11 rounded-[var(--radius-pill)] border border-white/80 bg-white px-2.5 py-1 text-[0.625rem] font-semibold text-accent">
        More Interviews
      </span>
      <span className="absolute bottom-0 left-1 rounded-[var(--radius-pill)] border border-white/80 bg-white px-2.5 py-1 text-[0.625rem] font-semibold text-success">
        Bigger Dreams
      </span>
    </div>
  );
}

function NextStepScorePreview({ score }: { score: number }) {
  return (
    <div
      aria-hidden="true"
      className="flex shrink-0 items-center justify-end gap-3"
    >
      <ScoreRing label="Resume Health Score" score={score} size="sm" tone="success" />
      <div className="hidden rounded-[var(--radius-control)] border border-line bg-surface-subtle p-2.5 sm:block">
        <FileText className="size-5 text-primary" strokeWidth={1.75} />
      </div>
    </div>
  );
}

function DashboardHero({
  displayName,
  nextStep,
  resumeHealth,
}: {
  displayName: string;
  nextStep: NextStep;
  resumeHealth: DashboardResumeHealth;
}) {
  const reportScore =
    resumeHealth.kind === "report" ? resumeHealth.score : null;

  return (
    <div className="workspace-dashboard-top">
      <section className="workspace-hero px-5 py-6 sm:px-7 sm:py-8 lg:pr-[12rem]">
        <div className="relative min-w-0">
          <p className="text-sm font-semibold text-primary">
            {greeting()}, {firstName(displayName)} 👋
          </p>
          <h1 className="balanced mt-2 font-display text-[clamp(1.45rem,2.6vw,2.1rem)] font-bold leading-[1.12] tracking-[-0.03em] text-foreground">
            Welcome to your Rezumi workspace, {displayName}.
          </h1>
          <p className="balanced mt-2.5 max-w-xl text-sm leading-6 text-muted">
            One reviewed career record upstream. Everything below is derived
            from it, and nothing changes without your decision.
          </p>
          <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
            <Link
              className={cn(
                buttonStyles.base,
                buttonStyles.primary,
                "w-full justify-center sm:w-auto",
              )}
              href="/resume-health/account"
            >
              Open Resume Studio
              <ArrowRight aria-hidden="true" className="size-4" />
            </Link>
            <Link
              className={cn(
                buttonStyles.base,
                buttonStyles.secondary,
                "w-full justify-center sm:w-auto",
              )}
              href="/career-profile"
            >
              View Career Record
            </Link>
          </div>
        </div>
        <HeroIllustration />
      </section>

      <section
        aria-labelledby="next-step-heading"
        className="workspace-next-step"
      >
        <div>
          <p className="flex items-center gap-1.5 text-[0.6875rem] font-semibold uppercase tracking-[0.1em] text-muted">
            <Sparkles aria-hidden="true" className="size-3.5 text-primary" />
            Next best step
          </p>
          <h2
            className="mt-2 text-[0.9375rem] font-semibold leading-snug text-foreground"
            id="next-step-heading"
          >
            {nextStep.title}
          </h2>
          <p className="mt-2 text-xs leading-5 text-muted">
            {nextStep.description}
          </p>
        </div>

        <div className="mt-5 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <Link
            className={cn(
              buttonStyles.base,
              buttonStyles.primary,
              "w-full justify-center sm:w-auto",
            )}
            href={nextStep.href}
          >
            {nextStep.label}
            <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
          {reportScore !== null && <NextStepScorePreview score={reportScore} />}
        </div>
      </section>
    </div>
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
  autoImport?: ReactNode;
  displayName: string;
  onboardingComplete: boolean;
  resumeHealth?: DashboardResumeHealth;
  summary?: DashboardSummary;
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
    <main className="workspace-page space-y-4 sm:space-y-5" id="main-content">
      <DashboardHero
        displayName={displayName}
        nextStep={nextStep}
        resumeHealth={resumeHealth}
      />

      {autoImport}

      {activating && <ActivationChain steps={chain} />}

      <CareerRecordStats record={summary.record} />

      <ResumeHelpBanner />

      <div className="workspace-dashboard-main">
        <section
          aria-labelledby="resume-state-heading"
          className="workspace-panel min-w-0"
        >
          <div className="workspace-panel-header">
            <h2 id="resume-state-heading">Latest resume state</h2>
            <Link className="workspace-panel-link" href="/resume-health/account">
              Open
              <ArrowUpRight aria-hidden="true" className="size-3.5" />
            </Link>
          </div>
          <ResumeState resumeHealth={resumeHealth} />
        </section>

        <DashboardActivity resumeHealth={resumeHealth} summary={summary} />
      </div>

      <div className="workspace-secondary-zone">
        <AttentionPanel
          degraded={summary.attentionDegraded}
          items={summary.attention}
        />
        <PipelinePanel pipeline={summary.pipeline} />
      </div>

      {corpId && (
        <StandingTile corpId={corpId} record={summary.record} />
      )}

      <TruthLockNote />
    </main>
  );
}
