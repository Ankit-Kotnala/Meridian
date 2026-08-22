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
import { heroSubtitle } from "../lib/dashboard-user-copy";

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
        "Tell us your target role and preferences so recommendations fit how you actually want to work.",
      href: "/onboarding",
      label: "Continue setup",
      title: "Finish setting up your account",
    };
  }
  if (resumeHealth.kind === "review") {
    return {
      description:
        "Check what was pulled from your file and fix anything that looks wrong before it goes on your profile.",
      href: `/resume-health/account/review/${encodeURIComponent(resumeHealth.documentId)}`,
      label: "Review parsed fields",
      title: "Confirm what we read from your resume",
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
        "See the latest status on your file and what you can do if something stalled.",
      href: "/resume-health/account",
      label: "Check resume status",
      title: "See what's happening with your resume",
    };
  }
  if (resumeHealth.kind === "importReady") {
    return {
      description:
        "Your confirmed resume details are being added to your profile. Open it to see roles, skills, and contact info.",
      href: "/career-profile",
      label: "View my profile",
      title: "Your profile is being filled in",
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
        "Your resume was reviewed but no roles landed yet. Open your profile or refresh — they should appear shortly.",
      href: "/career-profile",
      label: "View my profile",
      title: "Add your resume details to your profile",
    };
  }
  if (experiences.kind === "count" && experiences.value === 0) {
    return {
      description:
        "Job matching, tailored documents, and interview prep all start from your work history. Add your first role to begin.",
      href: "/career-profile",
      label: "Add your first role",
      title: "Build your work history",
    };
  }
  if (resumeHealth.kind === "report") {
    return {
      description:
        "See what's strong, what's missing, and which changes are worth making — nothing applies until you choose it.",
      href: `/resume-health/account/report/${encodeURIComponent(resumeHealth.analysisId)}`,
      label: "Open my report",
      title: "Review your resume findings",
    };
  }
  return {
    description:
      "Upload a PDF or DOCX to pull in your experience faster. You'll review anything uncertain before it goes live.",
    href: "/resume-health/account",
    label: "Upload a resume",
    title: "Bring in your experience from a resume",
  };
}

function HeroIllustration({
  resumeHealth,
}: {
  resumeHealth: DashboardResumeHealth;
}) {
  const reportScore =
    resumeHealth.kind === "report" ? resumeHealth.score : null;

  return (
    <div
      aria-hidden="true"
      className="preview-float relative mx-auto w-full max-w-[15rem] lg:absolute lg:right-8 lg:top-1/2 lg:mx-0 lg:-translate-y-1/2"
    >
      <div className="absolute inset-0 rounded-full bg-white/50 blur-2xl" />
      <div className="relative rounded-2xl border border-white/80 bg-white/95 p-4 shadow-[0_12px_32px_-16px_rgb(10_41_26_/_0.2)]">
        <div className="flex items-center gap-2">
          <FileText className="size-5 text-primary" strokeWidth={1.75} />
          <span className="text-xs font-semibold text-primary">Your resume</span>
        </div>
        <div className="mt-3 space-y-2">
          <div className="h-1.5 w-full rounded-full bg-primary-soft" />
          <div className="h-1.5 w-4/5 rounded-full bg-primary-soft" />
          <div className="h-1.5 w-3/5 rounded-full bg-primary-soft" />
        </div>
        {reportScore !== null ? (
          <span className="absolute -right-2 -top-2 grid size-10 place-items-center rounded-full border-2 border-success bg-white text-xs font-bold text-success-strong">
            {reportScore}
          </span>
        ) : (
          <CheckCircle2
            className="absolute -right-2 -top-2 size-8 text-success"
            strokeWidth={2}
          />
        )}
      </div>
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
  summary,
}: {
  displayName: string;
  nextStep: NextStep;
  resumeHealth: DashboardResumeHealth;
  summary: DashboardSummary;
}) {
  const reportScore =
    resumeHealth.kind === "report" ? resumeHealth.score : null;
  const insight = heroSubtitle(summary, resumeHealth);

  return (
    <div className="workspace-dashboard-top">
      <section className="workspace-hero px-5 py-6 sm:px-7 sm:py-8 lg:pr-[12rem]">
        <div className="relative min-w-0">
          <p className="text-sm font-semibold text-primary">
            {greeting()}, {firstName(displayName)} 👋
          </p>
          <h1 className="balanced mt-2 font-display text-[clamp(1.45rem,2.6vw,2.1rem)] font-bold leading-[1.12] tracking-[-0.03em] text-foreground">
            {insight}
          </h1>
          <p className="balanced mt-2.5 max-w-xl text-sm leading-6 text-muted">
            This is your home base — profile, applications, resume feedback, and
            what needs your attention, all in one place.
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
              My resume
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
              My profile
            </Link>
          </div>
        </div>
        <HeroIllustration resumeHealth={resumeHealth} />
      </section>

      <section
        aria-labelledby="next-step-heading"
        className="workspace-next-step"
      >
        <div>
          <p className="flex items-center gap-1.5 text-[0.6875rem] font-semibold uppercase tracking-[0.1em] text-muted">
            <Sparkles aria-hidden="true" className="size-3.5 text-primary" />
            Your next move
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
        summary={summary}
      />

      {autoImport}

      <AttentionPanel
        degraded={summary.attentionDegraded}
        items={summary.attention}
      />

      <CareerRecordStats record={summary.record} />

      {activating && <ActivationChain steps={chain} />}

      <ResumeHelpBanner />

      <div className="workspace-dashboard-main">
        <section
          aria-labelledby="resume-state-heading"
          className="workspace-panel min-w-0"
        >
          <div className="workspace-panel-header">
            <h2 id="resume-state-heading">Your resume</h2>
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
        <PipelinePanel pipeline={summary.pipeline} />
      </div>

      {corpId && (
        <StandingTile corpId={corpId} record={summary.record} />
      )}

      <TruthLockNote />
    </main>
  );
}
