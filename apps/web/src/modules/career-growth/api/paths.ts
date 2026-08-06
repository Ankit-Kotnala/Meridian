import type { paths } from "@rezumi/contracts";

import { fillApiPath, type GeneratedApiPath } from "@/shared/api/api-path";
import { buildApiQueryString } from "@/shared/api/api-query-string";

type StaticPath = keyof paths;

export const careerGrowthPaths = {
  insights: "/api/v1/career-growth/insights" satisfies StaticPath,
  careerHealthAnalyses:
    "/api/v1/career-growth/career-health/analyses" satisfies StaticPath,
  careerHealthAnalysis: (analysisId: string) =>
    fillApiPath("/api/v1/career-growth/career-health/analyses/{analysis_id}", {
      analysis_id: analysisId,
    }),
  developmentItems:
    "/api/v1/career-growth/development-items" satisfies StaticPath,
  developmentItem: (itemId: string) =>
    fillApiPath("/api/v1/career-growth/development-items/{item_id}", {
      item_id: itemId,
    }),
  goals: "/api/v1/career-growth/goals" satisfies StaticPath,
  goal: (goalId: string) =>
    fillApiPath("/api/v1/career-growth/goals/{goal_id}", {
      goal_id: goalId,
    }),
  milestones: (goalId: string) =>
    fillApiPath("/api/v1/career-growth/goals/{goal_id}/milestones", {
      goal_id: goalId,
    }),
  milestone: (goalId: string, milestoneId: string) =>
    fillApiPath(
      "/api/v1/career-growth/goals/{goal_id}/milestones/{milestone_id}",
      {
        goal_id: goalId,
        milestone_id: milestoneId,
      },
    ),
  reviews: "/api/v1/career-growth/reviews" satisfies StaticPath,
  review: (reviewId: string) =>
    fillApiPath("/api/v1/career-growth/reviews/{review_id}", {
      review_id: reviewId,
    }),
  reviewFinalizations: (reviewId: string) =>
    fillApiPath("/api/v1/career-growth/reviews/{review_id}/finalizations", {
      review_id: reviewId,
    }),
  reviewVersions: (reviewId: string) =>
    fillApiPath("/api/v1/career-growth/reviews/{review_id}/versions", {
      review_id: reviewId,
    }),
} as const;

export function withCareerGrowthQuery(
  base: StaticPath | GeneratedApiPath,
  values: Parameters<typeof buildApiQueryString>[0],
): GeneratedApiPath {
  return `${base}${buildApiQueryString(values)}` as GeneratedApiPath;
}
