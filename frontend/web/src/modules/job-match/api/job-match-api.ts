"use client";

import { apiMutation, apiQuery } from "@/shared/api/browser-request";

import { jobMatchPaths, withQuery } from "./paths";
import type {
  ApplicationForJob,
  ApplyResume,
  Job,
  JobCatalogBrowse,
  JobCatalogSearch,
  JobCreateInput,
  JobImportInput,
  JobMatchAnalysis,
  JobPage,
  JobSourceKind,
  JobUpdateInput,
  OpportunityPriority,
  OpportunityPriorityInput,
  RequirementMatchPage,
  RolePreference,
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
  return apiMutation(path, init, { csrf: "session", retryAfterRefresh: true });
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

export async function getJobCatalogSuggestions(): Promise<JobCatalogSearch> {
  const response = await query(jobMatchPaths.jobCatalog);
  return (await response.json()) as JobCatalogSearch;
}

export async function saveJobCatalogListing(
  platform: string,
  externalId: string,
): Promise<Job> {
  const response = await mutate(jobMatchPaths.jobCatalogSave, {
    body: JSON.stringify({ platform, externalId }),
    method: "POST",
  });
  return (await response.json()) as Job;
}

export async function getJobCatalogRolePreferences(): Promise<RolePreference> {
  const response = await query(jobMatchPaths.jobCatalogRolePreferences);
  return (await response.json()) as RolePreference;
}

export async function setJobCatalogRolePreferences(
  roleTitles: string[],
): Promise<RolePreference> {
  const response = await mutate(jobMatchPaths.jobCatalogRolePreferences, {
    body: JSON.stringify({ roleTitles }),
    method: "PUT",
  });
  return (await response.json()) as RolePreference;
}

export async function browseJobCatalog(filters: {
  limit?: number;
  offset?: number;
  platform?: string;
  q?: string;
}): Promise<JobCatalogBrowse> {
  const response = await query(
    withQuery(jobMatchPaths.jobCatalogBrowse, {
      limit: filters.limit,
      offset: filters.offset,
      platform: filters.platform || undefined,
      q: filters.q || undefined,
    }),
  );
  return (await response.json()) as JobCatalogBrowse;
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

export async function listResumesForApply(): Promise<ApplyResume[]> {
  const response = await query(jobMatchPaths.applyResumes);
  const body = (await response.json()) as { items: ApplyResume[] };
  return body.items;
}

/** "Apply for me": creates the tracked application, ready for a pack. */
export async function createApplicationForJob(
  jobId: string,
  resumeVersionId: string,
): Promise<ApplicationForJob> {
  const response = await mutate(jobMatchPaths.applications, {
    body: JSON.stringify({
      jobId,
      resumeVersionId,
      stage: "ready_to_apply",
    }),
    headers: headers(undefined, crypto.randomUUID()),
    method: "POST",
  });
  return (await response.json()) as ApplicationForJob;
}

/** Generates the tailored resume + (if an Application Profile exists) the assisted-apply handoff. */
export async function generateAssistedApplyPack(
  applicationId: string,
): Promise<void> {
  await mutate(jobMatchPaths.applicationPacks(applicationId), {
    body: JSON.stringify({ includeKinds: ["tailored_resume"] }),
    headers: headers(undefined, crypto.randomUUID()),
    method: "POST",
  });
}
