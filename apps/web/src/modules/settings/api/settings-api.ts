"use client";

import type { components } from "@careeros/contracts";

import { apiMutation, apiQuery } from "@/shared/api/browser-request";

export type ProfileState = components["schemas"]["MeResponse"];
export type SessionState = components["schemas"]["SessionSummaryResponse"];
export type ConsentState = components["schemas"]["ConsentResponse"];
export type ConsentPurpose = components["schemas"]["ConsentRequest"]["purpose"];

function record(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null)
    throw new Error("Invalid API response.");
  return value as Record<string, unknown>;
}

function parseProfile(value: unknown): ProfileState {
  const candidate = record(value);
  if (
    typeof candidate.displayName !== "string" ||
    typeof candidate.email !== "string" ||
    typeof candidate.emailVerified !== "boolean" ||
    typeof candidate.locale !== "string" ||
    typeof candidate.timezone !== "string" ||
    typeof candidate.language !== "string" ||
    typeof candidate.writingStyle !== "string" ||
    typeof candidate.version !== "number"
  ) {
    throw new Error("Invalid profile response.");
  }
  return candidate as unknown as ProfileState;
}

export async function getProfile(): Promise<ProfileState> {
  return parseProfile(
    await (await apiQuery("/api/v1/me", { retryAfterRefresh: true })).json(),
  );
}

export async function updateProfile(
  profile: ProfileState,
  updates: Partial<ProfileState>,
): Promise<ProfileState> {
  const next = { ...profile, ...updates };
  const body = {
    displayName: next.displayName,
    industry: next.industry,
    language: next.language,
    locale: next.locale,
    preferredLocation: next.preferredLocation,
    seniority: next.seniority,
    targetRole: next.targetRole,
    timezone: next.timezone,
    workModel: next.workModel,
    writingStyle: next.writingStyle,
  } satisfies components["schemas"]["MeUpdateRequest"];
  const response = await apiMutation(
    "/api/v1/me",
    {
      method: "PATCH",
      headers: { "If-Match": `"${profile.version}"` },
      body: JSON.stringify(body),
    },
    { csrf: "session" },
  );
  return parseProfile(await response.json());
}

export async function getSessions(): Promise<SessionState[]> {
  const body = record(
    await (
      await apiQuery("/api/v1/auth/sessions", { retryAfterRefresh: true })
    ).json(),
  );
  if (!Array.isArray(body.data)) throw new Error("Invalid session response.");
  return body.data as SessionState[];
}

export async function revokeSession(sessionId: string): Promise<void> {
  await apiMutation(
    `/api/v1/auth/sessions/${encodeURIComponent(sessionId)}`,
    {
      method: "DELETE",
    },
    { csrf: "session" },
  );
}

export async function revokeAllSessions(): Promise<void> {
  await apiMutation(
    "/api/v1/auth/logout-all",
    { method: "POST" },
    { csrf: "session" },
  );
}

export async function getConsents(): Promise<ConsentState[]> {
  const body = record(
    await (
      await apiQuery("/api/v1/consents", { retryAfterRefresh: true })
    ).json(),
  );
  if (!Array.isArray(body.data)) throw new Error("Invalid consent response.");
  return body.data as ConsentState[];
}

export async function setConsent(
  purpose: ConsentPurpose,
  granted: boolean,
): Promise<ConsentState> {
  const body = {
    granted,
    purpose,
  } satisfies components["schemas"]["ConsentRequest"];
  const response = await apiMutation(
    "/api/v1/consents",
    {
      method: "POST",
      body: JSON.stringify(body),
    },
    { csrf: "session" },
  );
  return (await response.json()) as ConsentState;
}
