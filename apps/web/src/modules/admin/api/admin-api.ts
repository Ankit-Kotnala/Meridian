import { fillApiPath } from "@/shared/api/api-path";
import { apiMutation, apiQuery } from "@/shared/api/browser-request";

export type AdminMetrics = {
  environment: string;
  service_version: string;
  status: string;
  active_users_count: number;
  total_resumes_count: number;
  total_applications_count: number;
  subscriptions_by_tier: Record<string, number>;
  system_health: Record<string, string>;
};

export type DeadLetterJob = {
  id: string;
  job_type: string;
  user_id: string;
  attempts: number;
  max_attempts: number;
  last_error: string | null;
  failed_at: string;
};

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
  const body = (await response.json()) as { jobs: DeadLetterJob[] };
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
