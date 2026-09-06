"use client";

import {
  ApiRequestError,
  apiMutation,
  apiQuery,
} from "@/shared/api/browser-request";

import { careerGrowthPaths, withCareerGrowthQuery } from "./paths";
import type {
  CareerGrowthInsights,
  CareerHealth,
  CareerHealthPage,
  CareerReview,
  CareerReviewCreateInput,
  CareerReviewPage,
  CareerReviewReviseInput,
  ConfirmRoadmapInput,
  ConfirmRoadmapResult,
  DevelopmentItem,
  DevelopmentItemCreateInput,
  DevelopmentItemPage,
  DevelopmentItemUpdateInput,
  Goal,
  GoalCreateInput,
  GoalMilestone,
  GoalPage,
  GoalUpdateInput,
  MilestoneCreateInput,
  MilestoneUpdateInput,
  RoleRoadmap,
  SkillLibrary,
} from "./types";

function mutationHeaders({
  idempotencyKey,
  version,
}: {
  idempotencyKey?: string;
  version?: number;
}): HeadersInit {
  return {
    ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
    ...(version === undefined ? {} : { "If-Match": `"${version}"` }),
  };
}

async function query(
  path: Parameters<typeof apiQuery>[0],
  signal?: AbortSignal,
) {
  return apiQuery(path, {
    retryAfterRefresh: true,
    ...(signal ? { signal } : {}),
  });
}

async function mutate(
  path: Parameters<typeof apiMutation>[0],
  init: Parameters<typeof apiMutation>[1],
) {
  return apiMutation(path, init, {
    csrf: "session",
    retryAfterRefresh: true,
  });
}

type PageOptions = {
  cursor?: string;
  signal?: AbortSignal;
};

export async function getCareerGrowthInsights(
  signal?: AbortSignal,
): Promise<CareerGrowthInsights> {
  const response = await query(careerGrowthPaths.insights, signal);
  return (await response.json()) as CareerGrowthInsights;
}

export async function listGoals(options: PageOptions = {}): Promise<GoalPage> {
  const response = await query(
    withCareerGrowthQuery(careerGrowthPaths.goals, {
      cursor: options.cursor,
      limit: 100,
    }),
    options.signal,
  );
  return (await response.json()) as GoalPage;
}

export async function getGoal(goalId: string): Promise<Goal> {
  const response = await query(careerGrowthPaths.goal(goalId));
  return (await response.json()) as Goal;
}

export async function createGoal(
  input: GoalCreateInput,
  idempotencyKey: string,
): Promise<Goal> {
  const response = await mutate(careerGrowthPaths.goals, {
    body: JSON.stringify(input),
    headers: mutationHeaders({ idempotencyKey }),
    method: "POST",
  });
  return (await response.json()) as Goal;
}

export async function updateGoal(
  goal: Pick<Goal, "id" | "version">,
  input: GoalUpdateInput,
): Promise<Goal> {
  const response = await mutate(careerGrowthPaths.goal(goal.id), {
    body: JSON.stringify(input),
    headers: mutationHeaders(goal),
    method: "PUT",
  });
  return (await response.json()) as Goal;
}

export async function deleteGoal(
  goal: Pick<Goal, "id" | "version">,
): Promise<void> {
  await mutate(careerGrowthPaths.goal(goal.id), {
    headers: mutationHeaders(goal),
    method: "DELETE",
  });
}

export async function createMilestone(
  goalId: string,
  input: MilestoneCreateInput,
  idempotencyKey: string,
): Promise<GoalMilestone> {
  const response = await mutate(careerGrowthPaths.milestones(goalId), {
    body: JSON.stringify(input),
    headers: mutationHeaders({ idempotencyKey }),
    method: "POST",
  });
  return (await response.json()) as GoalMilestone;
}

export async function updateMilestone(
  milestone: Pick<GoalMilestone, "goalId" | "id" | "version">,
  input: MilestoneUpdateInput,
): Promise<GoalMilestone> {
  const response = await mutate(
    careerGrowthPaths.milestone(milestone.goalId, milestone.id),
    {
      body: JSON.stringify(input),
      headers: mutationHeaders(milestone),
      method: "PUT",
    },
  );
  return (await response.json()) as GoalMilestone;
}

export async function deleteMilestone(
  milestone: Pick<GoalMilestone, "goalId" | "id" | "version">,
): Promise<void> {
  await mutate(careerGrowthPaths.milestone(milestone.goalId, milestone.id), {
    headers: mutationHeaders(milestone),
    method: "DELETE",
  });
}

export async function listDevelopmentItems(
  options: PageOptions = {},
): Promise<DevelopmentItemPage> {
  const response = await query(
    withCareerGrowthQuery(careerGrowthPaths.developmentItems, {
      cursor: options.cursor,
      limit: 100,
    }),
    options.signal,
  );
  return (await response.json()) as DevelopmentItemPage;
}

export async function createDevelopmentItem(
  input: DevelopmentItemCreateInput,
  idempotencyKey: string,
): Promise<DevelopmentItem> {
  const response = await mutate(careerGrowthPaths.developmentItems, {
    body: JSON.stringify(input),
    headers: mutationHeaders({ idempotencyKey }),
    method: "POST",
  });
  return (await response.json()) as DevelopmentItem;
}

export async function updateDevelopmentItem(
  item: Pick<DevelopmentItem, "id" | "version">,
  input: DevelopmentItemUpdateInput,
): Promise<DevelopmentItem> {
  const response = await mutate(careerGrowthPaths.developmentItem(item.id), {
    body: JSON.stringify(input),
    headers: mutationHeaders(item),
    method: "PUT",
  });
  return (await response.json()) as DevelopmentItem;
}

export async function deleteDevelopmentItem(
  item: Pick<DevelopmentItem, "id" | "version">,
): Promise<void> {
  await mutate(careerGrowthPaths.developmentItem(item.id), {
    headers: mutationHeaders(item),
    method: "DELETE",
  });
}

export async function listCareerReviews(
  options: PageOptions = {},
): Promise<CareerReviewPage> {
  const response = await query(
    withCareerGrowthQuery(careerGrowthPaths.reviews, {
      cursor: options.cursor,
      limit: 100,
    }),
    options.signal,
  );
  return (await response.json()) as CareerReviewPage;
}

export async function getCareerReview(reviewId: string): Promise<CareerReview> {
  const response = await query(careerGrowthPaths.review(reviewId));
  return (await response.json()) as CareerReview;
}

export async function createCareerReview(
  input: CareerReviewCreateInput,
  idempotencyKey: string,
): Promise<CareerReview> {
  const response = await mutate(careerGrowthPaths.reviews, {
    body: JSON.stringify(input),
    headers: mutationHeaders({ idempotencyKey }),
    method: "POST",
  });
  return (await response.json()) as CareerReview;
}

export async function finalizeCareerReview(
  review: Pick<CareerReview, "id" | "version">,
  idempotencyKey: string,
): Promise<CareerReview> {
  const response = await mutate(
    careerGrowthPaths.reviewFinalizations(review.id),
    {
      headers: mutationHeaders({ ...review, idempotencyKey }),
      method: "POST",
    },
  );
  return (await response.json()) as CareerReview;
}

export async function reviseCareerReview(
  review: Pick<CareerReview, "id" | "version">,
  input: CareerReviewReviseInput,
): Promise<CareerReview> {
  const response = await mutate(careerGrowthPaths.reviewVersions(review.id), {
    body: JSON.stringify(input),
    headers: mutationHeaders(review),
    method: "POST",
  });
  return (await response.json()) as CareerReview;
}

export async function deleteCareerReview(
  review: Pick<CareerReview, "id" | "version">,
): Promise<void> {
  await mutate(careerGrowthPaths.review(review.id), {
    headers: mutationHeaders(review),
    method: "DELETE",
  });
}

export async function listCareerHealth(
  options: PageOptions = {},
): Promise<CareerHealthPage> {
  const response = await query(
    withCareerGrowthQuery(careerGrowthPaths.careerHealthAnalyses, {
      cursor: options.cursor,
      limit: 100,
    }),
    options.signal,
  );
  return (await response.json()) as CareerHealthPage;
}

export async function getCareerHealth(
  analysisId: string,
): Promise<CareerHealth> {
  const response = await query(
    careerGrowthPaths.careerHealthAnalysis(analysisId),
  );
  return (await response.json()) as CareerHealth;
}

export async function analyzeCareerHealth(
  idempotencyKey: string,
): Promise<CareerHealth> {
  const response = await mutate(careerGrowthPaths.careerHealthAnalyses, {
    headers: mutationHeaders({ idempotencyKey }),
    method: "POST",
  });
  return (await response.json()) as CareerHealth;
}

export async function deleteCareerHealth(
  analysis: Pick<CareerHealth, "id">,
): Promise<void> {
  await mutate(careerGrowthPaths.careerHealthAnalysis(analysis.id), {
    method: "DELETE",
  });
}

export async function getRoleRoadmap(
  signal?: AbortSignal,
): Promise<RoleRoadmap | null> {
  const response = await query(careerGrowthPaths.roadmap, signal);
  return (await response.json()) as RoleRoadmap | null;
}

export async function getSkillLibrary(
  skillName: string,
  signal?: AbortSignal,
): Promise<SkillLibrary> {
  const response = await query(
    withCareerGrowthQuery(careerGrowthPaths.skillLibrary, { skillName }),
    signal,
  );
  return (await response.json()) as SkillLibrary;
}

export async function confirmRoleRoadmap(
  input: ConfirmRoadmapInput,
): Promise<ConfirmRoadmapResult> {
  const response = await mutate(careerGrowthPaths.roadmapConfirm, {
    body: JSON.stringify(input),
    method: "POST",
  });
  return (await response.json()) as ConfirmRoadmapResult;
}

export function isVersionConflict(error: unknown): boolean {
  return (
    error instanceof ApiRequestError &&
    (error.failure.status === 409 || error.failure.status === 412)
  );
}

export { ApiRequestError };
