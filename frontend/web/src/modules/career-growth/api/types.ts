import type { components } from "@rezumi/contracts";

type ContractEvidenceLink = components["schemas"]["EvidenceLinkResponse"];
type ContractGoalMilestone = components["schemas"]["GoalMilestoneResponse"];
type ContractGoal = components["schemas"]["GoalResponse"];
type ContractDevelopmentItem = components["schemas"]["DevelopmentItemResponse"];
type ContractReviewVersion = components["schemas"]["ReviewVersionResponse"];
type ContractCareerReview = components["schemas"]["CareerReviewResponse"];
type PageMetadata = components["schemas"]["GoalPageResponse"]["page"];

export type EvidenceLink = ContractEvidenceLink & {
  supportStatus: "current" | "needs_review";
};
export type GoalMilestone = Omit<ContractGoalMilestone, "evidenceLinks"> & {
  evidenceLinks: EvidenceLink[];
};
export type Goal = Omit<ContractGoal, "evidenceLinks" | "milestones"> & {
  evidenceLinks: EvidenceLink[];
  milestones: GoalMilestone[];
};
export type GoalSummary = Pick<
  Goal,
  "id" | "status" | "targetDate" | "title" | "updatedAt" | "version"
> & {
  evidenceLinkCount: number;
  evidenceNeedsReviewCount: number;
  milestoneCount: number;
};
export type GoalPage = {
  data: GoalSummary[];
  page: PageMetadata;
};
export type GoalCreateInput = components["schemas"]["GoalCreateRequest"];
export type GoalUpdateInput = components["schemas"]["GoalUpdateRequest"];
export type MilestoneCreateInput =
  components["schemas"]["MilestoneCreateRequest"];
export type MilestoneUpdateInput =
  components["schemas"]["MilestoneUpdateRequest"];

export type DevelopmentItem = Omit<ContractDevelopmentItem, "evidenceLinks"> & {
  evidenceLinks: EvidenceLink[];
};
export type DevelopmentItemPage = {
  data: DevelopmentItem[];
  page: PageMetadata;
};
export type DevelopmentItemCreateInput =
  components["schemas"]["DevelopmentItemCreateRequest"];
export type DevelopmentItemUpdateInput =
  components["schemas"]["DevelopmentItemUpdateRequest"];
type ContractInsights = components["schemas"]["CareerGrowthInsightsResponse"];
export type CareerGrowthInsights = Omit<
  ContractInsights,
  "annualResumeRefreshes" | "promotionReadiness" | "skills"
> & {
  annualResumeRefreshes: DevelopmentItem[];
  promotionReadiness: Omit<ContractInsights["promotionReadiness"], "checks"> & {
    checks: Array<
      ContractInsights["promotionReadiness"]["checks"][number] & {
        evidenceCount: number;
      }
    >;
  };
  skills: Array<
    ContractInsights["skills"][number] & {
      evidenceCount: number;
    }
  >;
};

export type ReviewVersion = Omit<ContractReviewVersion, "evidenceLinks"> & {
  evidenceLinks: EvidenceLink[];
};
export type CareerReview = Omit<
  ContractCareerReview,
  "currentVersion" | "history"
> & {
  currentVersion: ReviewVersion;
  history: ReviewVersion[];
};
export type CareerReviewSummary = Pick<
  CareerReview,
  | "cadence"
  | "createdAt"
  | "id"
  | "latestStatus"
  | "latestVersionId"
  | "latestVersionNumber"
  | "periodEnd"
  | "periodStart"
  | "updatedAt"
  | "version"
> & {
  currentTitle: string;
  evidenceLinkCount: number;
  evidenceNeedsReviewCount: number;
  historyCount: number;
};
export type CareerReviewPage = {
  data: CareerReviewSummary[];
  page: PageMetadata;
};
export type CareerReviewCreateInput =
  components["schemas"]["CareerReviewCreateRequest"];
export type CareerReviewReviseInput =
  components["schemas"]["CareerReviewReviseRequest"];
export type ReviewContent = components["schemas"]["ReviewContentRequest"];

export type CareerHealth = components["schemas"]["CareerHealthResponse"];
export type CareerHealthSummary = Pick<
  CareerHealth,
  | "applicableComponentCount"
  | "applicableWeightBasisPoints"
  | "createdAt"
  | "disclaimer"
  | "displayScore"
  | "engineVersion"
  | "id"
  | "insufficientReason"
  | "label"
  | "rawScoreBasisPoints"
  | "status"
> & {
  findingCount: number;
};
export type CareerHealthPage = {
  data: CareerHealthSummary[];
  page: PageMetadata;
};
export type CareerHealthComponent =
  components["schemas"]["CareerHealthComponentResponse"];

export type RoleRoadmap = components["schemas"]["RoleRoadmapResponse"];
export type RoadmapStage = components["schemas"]["RoadmapStageResponse"];
export type RoadmapSkill = components["schemas"]["RoadmapSkillResponse"];
export type ConfirmRoadmapInput =
  components["schemas"]["ConfirmRoadmapRequest"];
export type ConfirmRoadmapResult =
  components["schemas"]["ConfirmRoadmapResponse"];
