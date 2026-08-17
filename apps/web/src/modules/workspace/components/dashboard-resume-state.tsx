import { ArrowRight, FileHeart } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Alert, Badge, buttonStyles, cn, ScoreRing } from "@rezumi/ui";

/**
 * Mirrors `DashboardResumeHealthState` from the Resume Health module. The
 * workspace home restates the shape instead of deep-importing another feature
 * module, so the dashboard stays a pure consumer of already-loaded state.
 */
export type DashboardResumeHealth =
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
    <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-start sm:gap-5 sm:p-6">
      <span className="grid size-10 shrink-0 place-items-center rounded-[var(--radius-control)] bg-primary-soft text-primary-strong">
        <FileHeart aria-hidden="true" className="size-5" />
      </span>
      <div className="min-w-0 flex-1">
        {badge}
        <h3
          className={cn(
            "font-semibold text-foreground",
            badge === undefined ? undefined : "mt-2.5",
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
        title="No resume data yet"
      >
        Upload a real PDF or DOCX, review uncertain parsing, and calculate an
        explainable internal measurement.
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
        title={`Preparing ${resumeHealth.filename}`}
      >
        The file remains quarantined while the protected worker scans and parses
        it.
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
        title="Check the parsed fields"
      >
        Rezumi extracted structured information from {resumeHealth.filename}.
        Confirm or correct it before analysis.
      </StatePanel>
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
    <div className="grid gap-5 p-5 sm:p-6 md:grid-cols-[9rem_minmax(0,1fr)] md:items-center">
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
        <h3 className="mt-2.5 font-semibold text-foreground">
          Latest report for {resumeHealth.filename}
        </h3>
        <p className="mt-1.5 max-w-2xl text-xs leading-5 text-muted">
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
