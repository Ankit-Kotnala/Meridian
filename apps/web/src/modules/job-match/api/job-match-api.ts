"use client";

import { apiMutation, apiQuery } from "@/shared/api/browser-request";

import { jobMatchPaths, withQuery } from "./paths";
import type {
  Job,
  JobCreateInput,
  JobImportInput,
  JobMatchAnalysis,
  JobPage,
  JobSourceKind,
  JobUpdateInput,
  OpportunityPriority,
  OpportunityPriorityInput,
  RequirementMatchPage,
} from "./types";

function headers(version?: number, idempotencyKey?: string): HeadersInit {
  return {
    ...(version === undefined ? {} : { "If-Match": `"${version}"` }),
    ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
  };
}

async function query(path: Parameters<typeof apiQuery>[0]) {
  return apiQuery(path, { retryAfterRefresh: true });
}

async function mutate(
  path: Parameters<typeof apiMutation>[0],
  init: Parameters<typeof apiMutation>[1],
) {
  return apiMutation(path, init, { csrf: "session" });
}

export async function getJobs(filters: {
  limit?: number;
  q?: string;
  sourceKind?: JobSourceKind | "";
  targetRoleId?: string;
}): Promise<JobPage> {
  const response = await query(
    withQuery(jobMatchPaths.jobs, {
      limit: filters.limit,
      q: filters.q || undefined,
      sourceKind: filters.sourceKind || undefined,
      targetRoleId: filters.targetRoleId,
    }),
  );
  return (await response.json()) as JobPage;
}

export async function createJob(input: JobCreateInput): Promise<Job> {
  const response = await mutate(jobMatchPaths.jobs, {
    body: JSON.stringify(input),
    headers: headers(undefined, crypto.randomUUID()),
    method: "POST",
  });
  return (await response.json()) as Job;
}

export async function importJob(input: JobImportInput): Promise<Job> {
  const response = await mutate(jobMatchPaths.importJob, {
    body: JSON.stringify(input),
    headers: headers(undefined, crypto.randomUUID()),
    method: "POST",
  });
  return (await response.json()) as Job;
}

export async function updateJob(job: Job, input: JobUpdateInput): Promise<Job> {
  const response = await mutate(jobMatchPaths.job(job.id), {
    body: JSON.stringify(input),
    headers: headers(job.version),
    method: "PATCH",
  });
  return (await response.json()) as Job;
}

export async function deleteJob(job: Job): Promise<void> {
  await mutate(jobMatchPaths.job(job.id), {
    headers: headers(job.version),
    method: "DELETE",
  });
}

export async function analyzeJob(jobId: string): Promise<JobMatchAnalysis> {
  const response = await mutate(jobMatchPaths.jobAnalyze(jobId), {
    headers: headers(undefined, crypto.randomUUID()),
    method: "POST",
  });
  return (await response.json()) as JobMatchAnalysis;
}

export async function getAnalysis(
  analysisId: string,
): Promise<JobMatchAnalysis> {
  return (await (
    await query(jobMatchPaths.analysis(analysisId))
  ).json()) as JobMatchAnalysis;
}

export async function getAnalysisRequirements(
  analysisId: string,
): Promise<RequirementMatchPage> {
  return (await (
    await query(jobMatchPaths.analysisRequirements(analysisId))
  ).json()) as RequirementMatchPage;
}

export async function prioritizeOpportunity(
  jobId: string,
  input: OpportunityPriorityInput,
): Promise<OpportunityPriority> {
  const response = await mutate(
    jobMatchPaths.opportunityPriorityForJob(jobId),
    {
      body: JSON.stringify(input),
      headers: headers(undefined, crypto.randomUUID()),
      method: "POST",
    },
  );
  return (await response.json()) as OpportunityPriority;
}
