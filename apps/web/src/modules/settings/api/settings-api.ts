"use client";

import type { components } from "@careeros/contracts";

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
export type AccountOperation =
  components["schemas"]["AccountOperationResponse"];
export type AccountOperationCreated =
  components["schemas"]["AccountOperationCreatedResponse"];
export type AccountExportDownload =
  components["schemas"]["AccountExportDownloadResponse"];

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
    fillApiPath("/api/v1/auth/sessions/{session_id}", {
      session_id: sessionId,
    }),
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
    { csrf: "session" },
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
    { csrf: "session" },
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
    { csrf: "session" },
  );
  return parseReminderPreferences(await response.json());
}
const activeAccountOperationStatuses = new Set<AccountOperation["status"]>([
  "queued",
  "running",
  "retryWait",
]);

function parseAccountOperation(value: unknown): AccountOperation {
  const candidate = record(value);
  if (
    typeof candidate.id !== "string" ||
    !["export", "deletion"].includes(String(candidate.kind)) ||
    ![
      "queued",
      "running",
      "retryWait",
      "succeeded",
      "blocked",
      "deadLettered",
      "expired",
    ].includes(String(candidate.status)) ||
    typeof candidate.attempts !== "number" ||
    typeof candidate.maxAttempts !== "number" ||
    typeof candidate.requestedAt !== "string" ||
    typeof candidate.updatedAt !== "string"
  ) {
    throw new Error("Invalid account operation response.");
  }
  return candidate as unknown as AccountOperation;
}

function parseAccountOperationCreated(value: unknown): AccountOperationCreated {
  const operation = parseAccountOperation(value);
  const candidate = record(value);
  if (
    typeof candidate.operationToken !== "string" ||
    candidate.operationToken.length < 80
  ) {
    throw new Error("Invalid account operation capability.");
  }
  return { ...operation, operationToken: candidate.operationToken };
}

function operationHeaders(operationToken: string): HeadersInit {
  return { "X-Account-Operation-Token": operationToken };
}

export async function requestAccountExport(
  idempotencyKey: string,
): Promise<AccountOperationCreated> {
  const response = await apiMutation(
    "/api/v1/account-exports",
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
    },
    { csrf: "session" },
  );
  return parseAccountOperationCreated(await response.json());
}

export async function requestAccountDeletion(
  idempotencyKey: string,
): Promise<AccountOperationCreated> {
  const response = await apiMutation(
    "/api/v1/account-deletions",
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
    },
    { csrf: "session" },
  );
  return parseAccountOperationCreated(await response.json());
}

export async function getAccountOperation(
  operationId: string,
  operationToken: string,
  signal?: AbortSignal,
): Promise<AccountOperation> {
  const response = await apiQuery(
    fillApiPath("/api/v1/account-operations/{operation_id}", {
      operation_id: operationId,
    }),
    {
      headers: operationHeaders(operationToken),
      ...(signal ? { signal } : {}),
    },
  );
  return parseAccountOperation(await response.json());
}

export async function createAccountExportDownload(
  operationId: string,
  operationToken: string,
): Promise<AccountExportDownload> {
  const response = await apiQuery(
    fillApiPath("/api/v1/account-operations/{operation_id}/download", {
      operation_id: operationId,
    }),
    { headers: operationHeaders(operationToken) },
  );
  const candidate = record(await response.json());
  if (
    typeof candidate.downloadUrl !== "string" ||
    typeof candidate.expiresInSeconds !== "number"
  ) {
    throw new Error("Invalid account export download response.");
  }
  return candidate as unknown as AccountExportDownload;
}

type WaitForAccountOperationOptions = {
  intervalMs?: number;
  onUpdate?: (operation: AccountOperation) => void;
  signal?: AbortSignal;
  timeoutMs?: number;
};

function waitForDelay(milliseconds: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(signal.reason ?? new DOMException("Aborted", "AbortError"));
      return;
    }
    const onAbort = () => {
      window.clearTimeout(timeout);
      reject(signal?.reason ?? new DOMException("Aborted", "AbortError"));
    };
    const timeout = window.setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, milliseconds);
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

export async function waitForAccountOperation(
  initial: AccountOperationCreated,
  options: WaitForAccountOperationOptions = {},
): Promise<AccountOperation> {
  const intervalMs = options.intervalMs ?? 1_000;
  const deadline = Date.now() + (options.timeoutMs ?? 120_000);
  let current: AccountOperation = initial;
  options.onUpdate?.(current);

  while (activeAccountOperationStatuses.has(current.status)) {
    if (Date.now() >= deadline) return current;
    await waitForDelay(intervalMs, options.signal);
    current = await getAccountOperation(
      current.id,
      initial.operationToken,
      options.signal,
    );
    options.onUpdate?.(current);
  }
  return current;
}
