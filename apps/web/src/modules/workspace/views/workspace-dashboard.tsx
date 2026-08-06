import {
  ArrowRight,
  Archive,
  BadgeCheck,
  FileHeart,
  NotebookPen,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import Link from "next/link";

import {
  Alert,
  Badge,
  buttonStyles,
  cn,
  EmptyState,
  PageHeader,
  ScoreRing,
  SectionHeader,
} from "@rezumi/ui";

type DashboardResumeHealth =
  | { kind: "empty" }
  | { kind: "error" }
  | { filename: string; kind: "deleting" }
  | { filename: string; kind: "failed" }
  | { filename: string; kind: "processing" }
  | { documentId: string; filename: string; kind: "review" }
  | {
      analysisId: string;
      disclaimer: string;
      filename: string;
      kind: "report";
      score: number | null;
      scoreBand: "developing" | "needsAttention" | "strong" | null;
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
  if (resumeHealth.kind === "report") {
    return {
      description:
        "Review the explainable findings, then choose which changes are worth considering. Nothing is changed automatically.",
      href: `/resume-health/account/report/${encodeURIComponent(resumeHealth.analysisId)}`,
      label: "Review findings",
      title: "Review your latest resume report",
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
  return {
    description:
      "A resume is optional, but adding one can accelerate your career record. You will review uncertain parsing before analysis.",
    href: "/resume-health/account",
    label: "Upload a resume",
    title: "Add a resume when you are ready",
  };
}

function ResumeState({
  resumeHealth,
}: {
  resumeHealth: DashboardResumeHealth;
}) {
  if (resumeHealth.kind === "empty") {
    return (
      <EmptyState
        action={
          <Link
            className={cn(buttonStyles.base, buttonStyles.primary)}
            href="/resume-health/account"
          >
            Upload a resume <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
        }
        className="min-h-56 border-0 bg-transparent shadow-none"
        description="Upload a real PDF or DOCX, review uncertain parsing, and calculate an explainable internal measurement."
        title="No resume data yet"
      />
    );
  }
  if (resumeHealth.kind === "processing") {
    return (
      <div className="p-5 sm:p-6">
        <Badge tone="warning">Processing</Badge>
        <h3 className="mt-3 font-semibold text-foreground">
          Preparing {resumeHealth.filename}
        </h3>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
          The file remains quarantined while the protected worker scans and
          parses it.
        </p>
        <Link
          className={cn(buttonStyles.base, buttonStyles.secondary, "mt-4")}
          href="/resume-health/account"
        >
          View document status
        </Link>
      </div>
    );
  }
  if (resumeHealth.kind === "deleting") {
    return (
      <div className="p-5 sm:p-6">
        <Alert title="Deletion in progress" tone="info">
          {resumeHealth.filename} is completing durable source and derivative
          cleanup. Refresh this page after the job finishes.
          <Link className="text-link mt-3 block" href="/resume-health/account">
            Open Resume health
          </Link>
        </Alert>
      </div>
    );
  }
  if (resumeHealth.kind === "review") {
    return (
      <div className="p-5 sm:p-6">
        <Badge tone="warning">Review required</Badge>
        <h3 className="mt-3 font-semibold text-foreground">
          Check the parsed fields
        </h3>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
          Rezumi extracted structured information from {resumeHealth.filename}.
          Confirm or correct it before analysis.
        </p>
        <Link
          className={cn(buttonStyles.base, buttonStyles.primary, "mt-4")}
          href={`/resume-health/account/review/${encodeURIComponent(resumeHealth.documentId)}`}
        >
          Review parsed resume
        </Link>
      </div>
    );
  }
  if (resumeHealth.kind === "failed") {
    return (
      <div className="p-5 sm:p-6">
        <Alert title="Document needs attention" tone="danger">
          {resumeHealth.filename} could not be safely processed. Open Resume
          health to delete it or try a clean supported file.
          <Link className="text-link mt-3 block" href="/resume-health/account">
            Open Resume health
          </Link>
        </Alert>
      </div>
    );
  }
  if (resumeHealth.kind === "error") {
    return (
      <div className="p-5 sm:p-6">
        <Alert title="Resume Health unavailable" tone="danger">
          Your private resume state could not be loaded. No document was
          changed. Refresh the page or open Resume health to try again.
          <Link className="text-link mt-3 block" href="/resume-health/account">
            Open Resume health
          </Link>
        </Alert>
      </div>
    );
  }
  return (
    <div className="grid gap-6 p-5 sm:p-6 md:grid-cols-[9rem_minmax(0,1fr)] md:items-center">
      <div className="flex justify-center md:justify-start">
        {resumeHealth.score === null ? (
          <span className="grid size-28 place-items-center rounded-full border-8 border-surface-inset text-center text-xs font-bold text-muted">
            Score unavailable
          </span>
        ) : (
          <ScoreRing
            label="Resume Health Score"
            score={resumeHealth.score}
            tone={resumeHealth.scoreBand === "strong" ? "success" : "warning"}
          />
        )}
      </div>
      <div>
        <Badge
          tone={resumeHealth.scoreBand === "strong" ? "success" : "warning"}
        >
          Internal Rezumi measure
        </Badge>
        <h3 className="mt-3 font-semibold text-foreground">
          Latest report for {resumeHealth.filename}
        </h3>
        <p className="mt-2 max-w-2xl text-xs leading-5 text-muted">
          {resumeHealth.disclaimer}
        </p>
        <Link
          className={cn(buttonStyles.base, buttonStyles.primary, "mt-4")}
          href={`/resume-health/account/report/${encodeURIComponent(resumeHealth.analysisId)}`}
        >
          Open full report <ArrowRight aria-hidden="true" className="size-4" />
        </Link>
      </div>
    </div>
  );
}

const foundationLinks = [
  {
    description: "Maintain roles, experience, skills, and preferences.",
    href: "/career-profile",
    icon: UserRound,
    label: "Career profile",
  },
  {
    description: "Connect claims to eligible, private supporting evidence.",
    href: "/evidence",
    icon: Archive,
    label: "Evidence vault",
  },
  {
    description: "Capture outcomes while the details are still fresh.",
    href: "/achievement-inbox",
    icon: NotebookPen,
    label: "Achievement inbox",
  },
] as const;

export function WorkspaceDashboard({
  displayName,
  onboardingComplete,
  resumeHealth = { kind: "empty" },
}: {
  displayName: string;
  onboardingComplete: boolean;
  resumeHealth?: DashboardResumeHealth;
}) {
  const nextStep = nextStepFor(onboardingComplete, resumeHealth);

  return (
    <main className="workspace-page" id="main-content">
      <PageHeader
        description="Start with the next useful action, then return to your structured career record whenever the underlying facts change."
        eyebrow="Home"
        metadata={
          <Badge tone="success">
            <ShieldCheck aria-hidden="true" className="size-3.5" /> Private
            account
          </Badge>
        }
        title={`Welcome to your Rezumi workspace, ${displayName}.`}
      />

      <div className="grid gap-7 lg:grid-cols-[minmax(0,1.35fr)_minmax(17rem,0.65fr)]">
        <section aria-labelledby="next-step-heading">
          <div className="overflow-hidden rounded-[var(--radius-card)] border border-primary/25 bg-primary-soft/45">
            <div className="p-5 sm:p-7">
              <p className="eyebrow text-primary-strong">Next best step</p>
              <h2
                className="mt-3 text-xl font-semibold tracking-[-0.025em] text-foreground"
                id="next-step-heading"
              >
                {nextStep.title}
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-strong">
                {nextStep.description}
              </p>
              <Link
                className={cn(buttonStyles.base, buttonStyles.primary, "mt-5")}
                href={nextStep.href}
              >
                {nextStep.label}
                <ArrowRight aria-hidden="true" className="size-4" />
              </Link>
            </div>
            <div className="flex items-center gap-2 border-t border-primary/20 bg-surface/55 px-5 py-3 text-xs text-muted sm:px-7">
              <BadgeCheck aria-hidden="true" className="size-4 text-primary" />
              You review factual changes before they become derived output.
            </div>
          </div>
        </section>

        <section aria-labelledby="foundation-heading">
          <SectionHeader
            description="The source of truth behind generated documents."
            id="foundation-heading"
            title="Career foundation"
          />
          <ul className="divide-y divide-line rounded-[var(--radius-card)] border border-line bg-surface">
            {foundationLinks.map(({ description, href, icon: Icon, label }) => (
              <li key={href}>
                <Link
                  className="group flex min-h-20 items-start gap-3 px-4 py-3.5 hover:bg-primary-soft/35"
                  href={href}
                >
                  <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-[var(--radius-small)] bg-surface-subtle text-muted-strong group-hover:bg-primary-soft group-hover:text-primary">
                    <Icon aria-hidden="true" className="size-4" />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold text-foreground">
                      {label}
                    </span>
                    <span className="mt-1 block text-xs leading-5 text-muted">
                      {description}
                    </span>
                  </span>
                  <ArrowRight
                    aria-hidden="true"
                    className="ml-auto mt-1 size-4 shrink-0 text-muted"
                  />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <section aria-labelledby="resume-state-heading" className="mt-9">
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

      <section
        aria-labelledby="operating-model-heading"
        className="mt-9 border-t border-line pt-7"
      >
        <div className="flex items-start gap-3">
          <FileHeart
            aria-hidden="true"
            className="mt-0.5 size-5 text-primary"
          />
          <div>
            <h2
              className="font-semibold text-foreground"
              id="operating-model-heading"
            >
              One career record, many grounded outputs
            </h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
              Rezumi keeps evidence and structured facts upstream. Resumes,
              application answers, interview stories, and networking drafts are
              downstream work products—not competing sources of truth.
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
