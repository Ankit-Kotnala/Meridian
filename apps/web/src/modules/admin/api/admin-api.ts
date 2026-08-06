import type { components } from "@rezumi/contracts";

import { fillApiPath } from "@/shared/api/api-path";
import { apiMutation, apiQuery } from "@/shared/api/browser-request";

export type AdminMetrics = components["schemas"]["SystemMetricsResponse"];
export type DeadLetterJob = components["schemas"]["DeadLetterJobResponse"];

export async function getAdminOverview(): Promise<AdminMetrics> {
  const response = await apiQuery("/api/v1/admin/overview", {
    retryAfterRefresh: true,
  });
  return (await response.json()) as AdminMetrics;
}

export async function getDeadLetterJobs(): Promise<DeadLetterJob[]> {
  const response = await apiQuery("/api/v1/admin/dead-letters", {
    retryAfterRefresh: true,
  });
  const body =
    (await response.json()) as components["schemas"]["DeadLetterJobListResponse"];
  return body.jobs;
}

export async function retryDeadLetterJob(jobId: string): Promise<void> {
  await apiMutation(
    fillApiPath("/api/v1/admin/dead-letters/{job_id}/retry", {
      job_id: jobId,
    }),
    { method: "POST" },
    { csrf: "session", retryAfterRefresh: true },
  );
}
