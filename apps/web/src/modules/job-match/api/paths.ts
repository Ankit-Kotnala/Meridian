import type { GeneratedApiPath } from "@/shared/api/api-path";
import { buildApiQueryString } from "@/shared/api/api-query-string";

function path(value: string): GeneratedApiPath {
  if (!value.startsWith("/api/v1/") || /[\s#]/.test(value)) {
    throw new Error("Invalid Job Match API path.");
  }
  return value as GeneratedApiPath;
}

function resource(base: string, id: string): GeneratedApiPath {
  if (!id) throw new Error("A resource identifier is required.");
  return path(`${base}/${encodeURIComponent(id)}`);
}

export const jobMatchPaths = {
  analysis: (id: string) => resource("/api/v1/job-match-analyses", id),
  analysisRequirements: (id: string) =>
    path(`/api/v1/job-match-analyses/${encodeURIComponent(id)}/requirements`),
  importJob: path("/api/v1/jobs/import"),
  job: (id: string) => resource("/api/v1/jobs", id),
  jobAnalyze: (id: string) =>
    path(`/api/v1/jobs/${encodeURIComponent(id)}/analyze`),
  jobs: path("/api/v1/jobs"),
  opportunityPriority: (id: string) =>
    resource("/api/v1/opportunity-priorities", id),
  opportunityPriorityForJob: (id: string) =>
    path(`/api/v1/jobs/${encodeURIComponent(id)}/opportunity-priority`),
} as const;

export function withQuery(
  base: GeneratedApiPath,
  values: Parameters<typeof buildApiQueryString>[0],
): GeneratedApiPath {
  return path(`${base}${buildApiQueryString(values)}`);
}
