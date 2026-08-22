import { ArrowRight, FileHeart } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Alert, Badge, buttonStyles, cn, ScoreRing } from "@rezumi/ui";

export type DashboardResumeHealth =
  | { kind: "empty" }
  | { kind: "error" }
  | { filename: string; kind: "deleting" }
  | { filename: string; kind: "failed" }
  | { filename: string; kind: "processing" }
  | { documentId: string; filename: string; kind: "review" }
  | {
      documentId: string;
      filename: string;
      kind: "importReady";
      snapshotId: string;
    }
  | {
      analysisId: string;
      disclaimer: string;
      documentId: string;
      filename: string;
      kind: "report";
      score: number | null;
      scoreBand: "developing" | "needsAttention" | "strong" | null;
      snapshotId: string;
      importSnapshotId?: string;
    };

function StatePanel({
  action,
  badge,
  children,
  title,
}: {
  action?: ReactNode;
  badge?: ReactNode;
  children: ReactNode;
  title: string;
}) {
  return (
    <div className="flex flex-1 flex-col gap-3 px-4 pb-5 pt-4 sm:px-5">
      <span className="grid size-10 shrink-0 place-items-center rounded-[var(--radius-control)] bg-primary-soft text-primary-strong">
        <FileHeart aria-hidden="true" className="size-5" />
      </span>
      <div className="min-w-0 flex-1">
        {badge}
        <h3
          className={cn(
            "font-bold text-foreground",
            badge === undefined ? undefined : "mt-2",
          )}
        >
          {title}
        </h3>
        <div className="mt-1.5 max-w-2xl text-sm leading-6 text-muted">
          {children}
        </div>
        {action && <div className="mt-4">{action}</div>}
      </div>
    </div>
  );
}

type ReportScoreBand = Extract<
  DashboardResumeHealth,
  { kind: "report" }
>["scoreBand"];

function scoreBandLabel(band: ReportScoreBand): string | undefined {
  if (band === "strong") return "Strong";
  if (band === "developing") return "Developing";
  if (band === "needsAttention") return "Needs attention";
  return undefined;
}

export function ResumeState({
  resumeHealth,
}: {
  resumeHealth: DashboardResumeHealth;
}) {
  if (resumeHealth.kind === "empty") {
    return (
      <StatePanel
        action={
          <Link
            className={cn(buttonStyles.base, buttonStyles.primary)}
            href="/resume-health/account"
          >
            Upload a resume <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
        }
        title="No resume on file yet"
      >
        Upload a PDF or DOCX to pull in your experience. You review anything
        uncertain before it appears on your profile.
      </StatePanel>
    );
  }

  if (resumeHealth.kind === "processing") {
    return (
      <StatePanel
        action={
          <Link
            className={cn(buttonStyles.base, buttonStyles.secondary)}
            href="/resume-health/account"
          >
            View document status
          </Link>
        }
        badge={<Badge tone="warning">Processing</Badge>}
        title={`Working on ${resumeHealth.filename}`}
      >
        Your file is being scanned and parsed. This usually finishes within a
        minute.
      </StatePanel>
    );
  }

  if (resumeHealth.kind === "review") {
    return (
      <StatePanel
        action={
          <Link
            className={cn(buttonStyles.base, buttonStyles.primary)}
            href={`/resume-health/account/review/${encodeURIComponent(resumeHealth.documentId)}`}
          >
            Review parsed resume
          </Link>
        }
        badge={<Badge tone="warning">Review required</Badge>}
        title="Confirm what we read from your resume"
      >
        We extracted structured details from {resumeHealth.filename}. Check
        them and fix anything that looks wrong before analysis.
      </StatePanel>
    );
  }

  if (resumeHealth.kind === "deleting") {
    return (
      <div className="flex-1 px-4 pb-5 pt-4 sm:px-5">
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

  if (resumeHealth.kind === "failed") {
    return (
      <div className="flex-1 px-4 pb-5 pt-4 sm:px-5">
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
      <div className="flex-1 px-4 pb-5 pt-4 sm:px-5">
        <Alert title="Could not load resume status" tone="danger">
          We could not reach your resume data. Nothing was changed. Refresh or
          open your resume page to try again.
          <Link className="text-link mt-3 block" href="/resume-health/account">
            Open my resume
          </Link>
        </Alert>
      </div>
    );
  }

  if (resumeHealth.kind === "importReady") {
    return (
      <StatePanel
        action={
          <Link
            className={cn(buttonStyles.base, buttonStyles.primary)}
            href="/career-profile"
          >
            Open career profile
          </Link>
        }
        badge={<Badge tone="success">Review complete</Badge>}
        title="Adding details to your profile"
      >
        {resumeHealth.filename} was reviewed. Your confirmed roles, skills,
        education, and contact details are being added to your profile.
      </StatePanel>
    );
  }

  if (resumeHealth.kind === "report") {
    const bandLabel = scoreBandLabel(resumeHealth.scoreBand);
    return (
      <div className="px-4 pb-5 pt-4 sm:px-5 sm:pb-6">
        <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-start sm:gap-6">
          <div className="flex shrink-0 flex-col items-center">
            {resumeHealth.score === null ? (
              <span className="grid size-36 place-items-center rounded-full border-[10px] border-surface-inset text-center text-xs font-bold text-muted">
                Score unavailable
              </span>
            ) : (
              <ScoreRing
                {...(bandLabel === undefined ? {} : { bandLabel })}
                label="Resume Health Score"
                score={resumeHealth.score}
                size="lg"
                tone={resumeHealth.scoreBand === "strong" ? "success" : "warning"}
              />
            )}
          </div>

          <div className="min-w-0 flex-1 text-center sm:text-left">
            <div className="flex flex-wrap justify-center gap-2 sm:justify-start">
              <Badge tone="primary">For your planning only</Badge>
              {bandLabel && (
                <Badge
                  tone={
                    resumeHealth.scoreBand === "strong" ? "success" : "warning"
                  }
                >
                  {bandLabel}
                </Badge>
              )}
            </div>
            <h3
              className="mt-2 text-sm font-bold text-foreground sm:text-base"
              title={resumeHealth.filename}
            >
              {resumeHealth.filename}
            </h3>
            <p className="mt-1 text-xs text-muted">Latest report</p>
            <p className="mt-3 text-xs leading-5 text-muted">
              {resumeHealth.disclaimer}
            </p>
            <Link
              className={cn(
                buttonStyles.base,
                buttonStyles.primary,
                "mt-4 inline-flex w-full justify-center sm:w-auto",
              )}
              href={`/resume-health/account/report/${encodeURIComponent(resumeHealth.analysisId)}`}
            >
              Open full report <ArrowRight aria-hidden="true" className="size-4" />
            </Link>
          </div>
        </div>
      </div>
    );
  }
}
