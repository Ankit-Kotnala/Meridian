"use client";

import type { components } from "@rezumi/contracts";

import { fillApiPath } from "@/shared/api/api-path";
import { apiMutation, apiQuery } from "@/shared/api/browser-request";

export type ProfileState = components["schemas"]["MeResponse"];
export type SessionState = components["schemas"]["SessionSummaryResponse"];
export type ConsentState = components["schemas"]["ConsentResponse"];
export type ConsentPurpose = components["schemas"]["ConsentRequest"]["purpose"];
export type ReminderPreferences =
  components["schemas"]["ReminderPreferencesResponse"];
export type SecurityActivity =
  components["schemas"]["SecurityActivityResponse"];
export type SettingsCapabilities =
  components["schemas"]["SettingsCapabilitiesResponse"];

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
    typeof candidate.id !== "string" ||
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

function parseCapabilities(value: unknown): SettingsCapabilities {
  const candidate = record(value);
  if (
    typeof candidate.hasPassword !== "boolean" ||
    typeof candidate.googleConnected !== "boolean" ||
    typeof candidate.googleOauthAvailable !== "boolean" ||
    candidate.reminderPreferencesAvailable !== true ||
    candidate.scheduledNotificationDeliveryAvailable !== false ||
    typeof candidate.accountExportAvailable !== "boolean" ||
    typeof candidate.accountDeletionAvailable !== "boolean" ||
    typeof candidate.billingAvailable !== "boolean" ||
    typeof candidate.guestResumeRetentionHours !== "number" ||
    candidate.accountResumeRetention !== "untilDeleted"
  ) {
    throw new Error("Invalid settings capability response.");
  }
  return candidate as unknown as SettingsCapabilities;
}

function parseReminderPreferences(value: unknown): ReminderPreferences {
  const candidate = record(value);
  if (
    typeof candidate.enabled !== "boolean" ||
    (candidate.dayOfMonth !== null &&
      candidate.dayOfMonth !== undefined &&
      typeof candidate.dayOfMonth !== "number") ||
    typeof candidate.timezone !== "string" ||
    typeof candidate.updatedAt !== "string" ||
    typeof candidate.version !== "number"
  ) {
    throw new Error("Invalid reminder preference response.");
  }
  return candidate as unknown as ReminderPreferences;
}

function parseSecurityActivity(value: unknown): SecurityActivity[] {
  const candidate = record(value);
  if (!Array.isArray(candidate.data)) {
    throw new Error("Invalid security activity response.");
  }
  return candidate.data.map((item) => {
    const activity = record(item);
    if (
      typeof activity.id !== "string" ||
      typeof activity.eventType !== "string" ||
      !["success", "accepted", "denied", "failed"].includes(
        String(activity.outcome),
      ) ||
      typeof activity.occurredAt !== "string" ||
      typeof activity.currentSession !== "boolean"
    ) {
      throw new Error("Invalid security activity response.");
    }
    return activity as unknown as SecurityActivity;
  });
}

export async function getProfile(): Promise<ProfileState> {
  return parseProfile(
    await (await apiQuery("/api/v1/me", { retryAfterRefresh: true })).json(),
  );
}

/**
 * Read the two career-record counts the Corp ID tier depends on.
 *
 * Failure is not fatal: a missing count reports zero contribution so the tier
 * degrades downward rather than claiming standing the account has not earned.
 */
export async function getCorpIdChecks(): Promise<{
  confirmedEvidence: number;
  experiences: number;
}> {
  async function count(
    path: "/api/v1/evidence" | "/api/v1/experiences",
    keep: (item: Record<string, unknown>) => boolean,
  ): Promise<number> {
    try {
      const body: unknown = await (
        await apiQuery(path, { retryAfterRefresh: true })
      ).json();
      const data = (body as { data?: unknown } | null)?.data;
      if (!Array.isArray(data)) return 0;
      return data.filter(
        (item): boolean =>
          typeof item === "object" &&
          item !== null &&
          keep(item as Record<string, unknown>),
      ).length;
    } catch {
      return 0;
    }
  }

  const [confirmedEvidence, experiences] = await Promise.all([
    count(
      "/api/v1/evidence",
      (item) => item.state === "confirmed" || item.state === "verified",
    ),
    count("/api/v1/experiences", () => true),
  ]);
  return { confirmedEvidence, experiences };
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
    { csrf: "session", retryAfterRefresh: true },
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
    fillApiPath("/api/v1/auth/sessions/{session_id}", {
      session_id: sessionId,
    }),
    {
      method: "DELETE",
    },
    { csrf: "session", retryAfterRefresh: true },
  );
}

export async function revokeAllSessions(): Promise<void> {
  await apiMutation(
    "/api/v1/auth/logout-all",
    { method: "POST" },
    { csrf: "session", retryAfterRefresh: true },
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
    { csrf: "session", retryAfterRefresh: true },
  );
  return (await response.json()) as ConsentState;
}

export async function getSettingsCapabilities(): Promise<SettingsCapabilities> {
  return parseCapabilities(
    await (
      await apiQuery("/api/v1/settings", { retryAfterRefresh: true })
    ).json(),
  );
}

export async function changePassword(
  currentPassword: string | null,
  newPassword: string,
): Promise<void> {
  const body = {
    currentPassword,
    newPassword,
  } satisfies components["schemas"]["ChangePasswordRequest"];
  await apiMutation(
    "/api/v1/auth/change-password",
    {
      method: "POST",
      body: JSON.stringify(body),
    },
    { csrf: "session", retryAfterRefresh: true },
  );
}

export async function exportAccountData(): Promise<Record<string, unknown>> {
  const response = await apiQuery("/api/v1/account/export", {
    retryAfterRefresh: true,
  });
  return (await response.json()) as Record<string, unknown>;
}

export async function deleteAccount(): Promise<void> {
  await apiMutation(
    "/api/v1/account",
    { method: "DELETE" },
    { csrf: "session", retryAfterRefresh: true },
  );
}

export async function getSecurityActivity(): Promise<SecurityActivity[]> {
  return parseSecurityActivity(
    await (
      await apiQuery("/api/v1/security-activity", {
        retryAfterRefresh: true,
      })
    ).json(),
  );
}

export async function disconnectGoogle(): Promise<void> {
  await apiMutation(
    "/api/v1/auth/connections/google",
    { method: "DELETE" },
    { csrf: "session", retryAfterRefresh: true },
  );
}

export async function getReminderPreferences(): Promise<ReminderPreferences> {
  return parseReminderPreferences(
    await (
      await apiQuery("/api/v1/achievements/reminder-preferences", {
        retryAfterRefresh: true,
      })
    ).json(),
  );
}

export async function updateReminderPreferences(
  current: ReminderPreferences,
  input: components["schemas"]["ReminderPreferencesUpdateRequest"],
): Promise<ReminderPreferences> {
  const response = await apiMutation(
    "/api/v1/achievements/reminder-preferences",
    {
      method: "PATCH",
      headers: { "If-Match": `"${current.version}"` },
      body: JSON.stringify(input),
    },
    { csrf: "session", retryAfterRefresh: true },
  );
  return parseReminderPreferences(await response.json());
}
