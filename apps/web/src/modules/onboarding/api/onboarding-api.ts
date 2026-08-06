"use client";

import type { components } from "@rezumi/contracts";

import {
  ApiRequestError,
  apiMutation,
  apiQuery,
} from "@/shared/api/browser-request";

export type OnboardingState = components["schemas"]["OnboardingResponse"];
export type OnboardingStep = OnboardingState["currentStep"];
export type OnboardingStatus = OnboardingState["status"];
export type HandoffStatus = OnboardingState["resumeHandoff"];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function parseOnboarding(value: unknown): OnboardingState {
  if (!isRecord(value)) throw new Error("Invalid onboarding response.");
  const requiredStrings = [
    "currentStep",
    "displayName",
    "language",
    "parsedReviewHandoff",
    "resumeHandoff",
    "status",
    "writingStyle",
  ] as const;
  if (
    requiredStrings.some((key) => typeof value[key] !== "string") ||
    typeof value.version !== "number" ||
    !Array.isArray(value.skippedSteps) ||
    !("latestResumeDocumentId" in value) ||
    !("resumeSafeErrorCode" in value)
  ) {
    throw new Error("Invalid onboarding response.");
  }
  return value as unknown as OnboardingState;
}

export async function getOnboarding(): Promise<OnboardingState> {
  return parseOnboarding(
    await (
      await apiQuery("/api/v1/onboarding", { retryAfterRefresh: true })
    ).json(),
  );
}

export async function updateOnboarding(
  current: OnboardingState,
  updates: Partial<OnboardingState>,
): Promise<OnboardingState> {
  const next = { ...current, ...updates };
  const body = {
    currentStep: next.currentStep,
    displayName: next.displayName,
    industry: next.industry,
    language: next.language,
    preferredLocation: next.preferredLocation,
    seniority: next.seniority,
    skippedSteps: next.skippedSteps,
    targetRole: next.targetRole,
    workModel: next.workModel,
    writingStyle: next.writingStyle,
  } satisfies components["schemas"]["OnboardingUpdateRequest"];
  const response = await apiMutation(
    "/api/v1/onboarding",
    {
      method: "PATCH",
      headers: { "If-Match": `"${current.version}"` },
      body: JSON.stringify(body),
    },
    { csrf: "session" },
  );
  return parseOnboarding(await response.json());
}

export { ApiRequestError as OnboardingRequestError };
