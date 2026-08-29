import Link from "next/link";

import { ScoreRing } from "@rezumi/ui";

import type { DashboardResumeHealth } from "./dashboard-resume-state";

/**
 * Compact resume-score link shown in the top bar. Per
 * docs/scoring-methodology.md, a compact view may use the short disclaimer
 * label instead of the full disclaimer paragraph only when the full
 * disclaimer is one accessible action away — here, the linked full report.
 */
export function HeaderResumeScore({
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
      className="group shrink-0"
      href={`/resume-health/account/report/${encodeURIComponent(resumeHealth.analysisId)}`}
      title="Internal Meridian measure — not an employer or ATS score"
    >
      <ScoreRing
        label="Resume Health Score"
        score={resumeHealth.score}
        size="sm"
        suffix=""
        tone="primary"
      />
    </Link>
  );
}
