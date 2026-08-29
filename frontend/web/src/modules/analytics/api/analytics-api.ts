"use client";

import { apiMutation, apiQuery } from "@/shared/api/browser-request";

import { analyticsPaths, withAnalyticsQuery } from "./paths";
import type {
  AnalyticsRefresh,
  AnalyticsRefreshInput,
  AnalyticsReport,
  AnalyticsScope,
} from "./types";

export async function getAnalyticsReport(
  filters: {
    scope: AnalyticsScope;
    timezone: string;
    windowEnd: string;
    windowStart: string;
  },
  signal?: AbortSignal,
): Promise<AnalyticsReport> {
  const response = await apiQuery(
    withAnalyticsQuery(analyticsPaths.report, filters),
    {
      retryAfterRefresh: true,
      ...(signal ? { signal } : {}),
    },
  );
  return (await response.json()) as AnalyticsReport;
}

export async function requestAnalyticsRefresh(
  input: AnalyticsRefreshInput,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<AnalyticsRefresh> {
  const response = await apiMutation(
    analyticsPaths.refreshes,
    {
      body: JSON.stringify(input),
      headers: { "Idempotency-Key": idempotencyKey },
      method: "POST",
      ...(signal ? { signal } : {}),
    },
    { csrf: "session", retryAfterRefresh: true },
  );
  return (await response.json()) as AnalyticsRefresh;
}

export async function getAnalyticsRefresh(
  jobId: string,
  signal?: AbortSignal,
): Promise<AnalyticsRefresh> {
  const response = await apiQuery(analyticsPaths.refresh(jobId), {
    retryAfterRefresh: true,
    ...(signal ? { signal } : {}),
  });
  return (await response.json()) as AnalyticsRefresh;
}
