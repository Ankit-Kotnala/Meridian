import type { paths } from "@careeros/contracts";

import { fillApiPath, type GeneratedApiPath } from "@/shared/api/api-path";
import { buildApiQueryString } from "@/shared/api/api-query-string";

type StaticPath = keyof paths;

export const analyticsPaths = {
  refreshes: "/api/v1/analytics/refreshes" satisfies StaticPath,
  refresh: (jobId: string) =>
    fillApiPath("/api/v1/analytics/refreshes/{job_id}", { job_id: jobId }),
  report: "/api/v1/analytics/report" satisfies StaticPath,
} as const;

export function withAnalyticsQuery(
  base: StaticPath | GeneratedApiPath,
  values: Parameters<typeof buildApiQueryString>[0],
): GeneratedApiPath {
  return `${base}${buildApiQueryString(values)}` as GeneratedApiPath;
}
