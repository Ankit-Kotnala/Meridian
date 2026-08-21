import {
  ArrowRight,
  ArrowUpRight,
  BadgeCheck,
  CheckCircle2,
  FileText,
  Sparkles,
  Target,
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
    <div aria-hidden="true" className="relative hidden h-full min-h-[10rem] w-full max-w-[14rem] xl:block">
      <div className="absolute inset-0 rounded-2xl border border-primary/10 bg-white/80 p-4 shadow-[0_8px_24px_-12px_rgb(11_61_46_/_0.15)]">
        <div className="flex items-center gap-2">
          <FileText className="size-5 text-primary" />
          <span className="text-xs font-bold text-primary">Resume</span>
        </div>
        <div className="mt-3 space-y-2">
          <div className="h-1.5 w-full rounded bg-primary-soft" />
          <div className="h-1.5 w-4/5 rounded bg-primary-soft" />
          <div className="h-1.5 w-3/5 rounded bg-primary-soft" />
        </div>
        <CheckCircle2 className="absolute -right-2 -top-2 size-8 text-success" />
      </div>
      <span className="absolute -left-3 top-6 rounded-full bg-white px-2.5 py-1 text-[0.625rem] font-bold text-primary shadow-sm">
        Better Resume
      </span>
      <span className="absolute -right-1 bottom-8 rounded-full bg-white px-2.5 py-1 text-[0.625rem] font-bold text-accent shadow-sm">
        More Interviews
      </span>
      <span className="absolute bottom-0 left-4 rounded-full bg-white px-2.5 py-1 text-[0.625rem] font-bold text-success shadow-sm">
        Bigger Dreams
      </span>
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
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(16rem,0.9fr)]">
      <section className="workspace-hero px-5 py-6 sm:px-7 sm:py-8">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-primary-strong">
              {greeting()}, {firstName(displayName)} 👋
            </p>
            <h1 className="balanced mt-2 font-display text-[clamp(1.5rem,2.8vw,2.15rem)] font-bold leading-[1.12] tracking-[-0.03em] text-foreground">
              Welcome to your Rezumi workspace, {displayName}.
            </h1>
            <p className="balanced mt-2.5 max-w-xl text-sm leading-6 text-muted">
              One reviewed career record upstream. Everything below is derived
              from it, and nothing changes without your decision.
            </p>
            <div className="mt-5 flex flex-wrap gap-3">
              <Link
                className={cn(buttonStyles.base, buttonStyles.primary)}
                href="/resume-health/account"
              >
                Open Resume Studio
                <ArrowRight aria-hidden="true" className="size-4" />
              </Link>
              <Link
                className={cn(buttonStyles.base, buttonStyles.secondary)}
                href="/career-profile"
              >
                View Career Record
              </Link>
            </div>
          </div>
          <HeroIllustration />
        </div>
      </section>

      <section
        aria-labelledby="next-step-heading"
        className="workspace-panel flex flex-col justify-between p-5"
      >
        <div>
          <p className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.08em] text-primary-strong">
            <Sparkles aria-hidden="true" className="size-3.5" />
            Next best step
          </p>
          <h2
            className="mt-2 text-base font-bold text-foreground"
            id="next-step-heading"
          >
            {nextStep.title}
          </h2>
          <p className="mt-1.5 text-xs leading-5 text-muted">
            {nextStep.description}
          </p>
        </div>

        <div className="mt-4 flex items-end justify-between gap-3">
          <Link
            className={cn(
              buttonStyles.base,
              buttonStyles.primary,
              "justify-center",
            )}
            href={nextStep.href}
          >
            {nextStep.label}
            <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
          {reportScore !== null && (
            <div aria-hidden="true">
              <ScoreRing
                label="Resume Health Score"
                score={reportScore}
                size="sm"
                tone="success"
              />
            </div>
          )}
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
    <main className="workspace-page space-y-4" id="main-content">
      <DashboardHero
        displayName={displayName}
        nextStep={nextStep}
        resumeHealth={resumeHealth}
      />

      {autoImport}

      {activating && <ActivationChain steps={chain} />}

      <CareerRecordStats record={summary.record} />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(18rem,0.85fr)]">
        <section
          aria-labelledby="resume-state-heading"
          className="workspace-panel min-w-0"
        >
          <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3.5 sm:px-5">
            <h2
              className="text-sm font-bold text-foreground"
              id="resume-state-heading"
            >
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

        <DashboardActivity resumeHealth={resumeHealth} summary={summary} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
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
