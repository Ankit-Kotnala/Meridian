import Link from "next/link";

import type { DashboardResumeHealth } from "./dashboard-resume-state";

/**
 * Compact resume-score value shown beside the Profile readiness heading. Per
 * docs/scoring-methodology.md, a compact view may use the short disclaimer
 * label instead of the full disclaimer paragraph only when the full
 * disclaimer is one accessible action away — here, the linked full report.
 */
export function ResumeScoreSummary({
  resumeHealth,
}: {
  resumeHealth: DashboardResumeHealth;
}) {
  if (resumeHealth.kind !== "report" || resumeHealth.score === null) {
    return null;
  }

  return (
    <Link
      aria-label={`Resume Health Score ${resumeHealth.score} out of 100 — internal Meridian measure, not an employer or applicant tracking system score. Open full report.`}
      className="shrink-0 text-[0.8125rem] font-semibold tabular-nums text-muted hover:text-foreground"
      href={`/resume-health/account/report/${encodeURIComponent(resumeHealth.analysisId)}`}
      title="Internal Meridian measure — not an employer or ATS score"
    >
      <span className="text-sm font-bold text-foreground">
        {resumeHealth.score}%
      </span>{" "}
      overall
    </Link>
  );
}
