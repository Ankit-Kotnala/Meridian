import type { ReactNode } from "react";

import { DashboardActivity } from "../components/dashboard-activity";
import {
  ActivationGate,
  shouldGateWorkspace,
} from "../components/dashboard-activation";
import {
  AttentionPanel,
  HomeStatCards,
  JobHuntPanel,
  PipelinePanel,
  ProfileReadinessPanel,
} from "../components/dashboard-sections";
import type { DashboardResumeHealth } from "../components/dashboard-resume-state";
import type { DashboardSummary } from "../server/dashboard-summary";

export type { DashboardResumeHealth };

const UNAVAILABLE = { kind: "unavailable" } as const;

const EMPTY_SUMMARY: DashboardSummary = {
  activation: { jobs: UNAVAILABLE, pendingImports: UNAVAILABLE },
  applications: [],
  attention: [],
  attentionDegraded: false,
  growth: UNAVAILABLE,
  jobHunt: UNAVAILABLE,
  pipeline: UNAVAILABLE,
  prepare: UNAVAILABLE,
  record: {
    achievements: UNAVAILABLE,
    evidence: UNAVAILABLE,
    evidenceConfirmed: UNAVAILABLE,
    experiences: UNAVAILABLE,
    skills: UNAVAILABLE,
  },
  resumes: UNAVAILABLE,
};

export function WorkspaceDashboard({
  autoImport,
  displayName,
  onboardingComplete,
  resumeHealth = { kind: "empty" },
  summary = EMPTY_SUMMARY,
}: {
  autoImport?: ReactNode;
  displayName: string;
  onboardingComplete: boolean;
  resumeHealth?: DashboardResumeHealth;
  summary?: DashboardSummary;
}) {
  if (onboardingComplete && shouldGateWorkspace(resumeHealth, summary)) {
    return <ActivationGate displayName={displayName} />;
  }

  return (
    <main className="workspace-page space-y-3 sm:space-y-4" id="main-content">
      {autoImport}

      <HomeStatCards
        pipeline={summary.pipeline}
        record={summary.record}
        resumes={summary.resumes}
      />

      <div className="grid grid-cols-1 gap-4 sm:gap-5 lg:grid-cols-3">
        <div className="flex flex-col gap-4 sm:gap-5 lg:col-span-2">
          <AttentionPanel
            degraded={summary.attentionDegraded}
            items={summary.attention}
          />

          <PipelinePanel
            applications={summary.applications}
            pipeline={summary.pipeline}
          />
        </div>

        <div className="flex flex-col gap-4 sm:gap-5">
          <ProfileReadinessPanel
            pipeline={summary.pipeline}
            record={summary.record}
          />

          <JobHuntPanel jobHunt={summary.jobHunt} />

          <DashboardActivity resumeHealth={resumeHealth} summary={summary} />
        </div>
      </div>
    </main>
  );
}
