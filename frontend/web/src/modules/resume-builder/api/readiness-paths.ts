import type { GeneratedApiPath } from "@/shared/api/api-path";
import { buildApiQueryString } from "@/shared/api/api-query-string";

function path(value: string): GeneratedApiPath {
  if (!value.startsWith("/api/v1/") || /[\s#]/.test(value)) {
    throw new Error("Invalid resume builder readiness API path.");
  }
  return value as GeneratedApiPath;
}

function withQuery(
  base: string,
  values: Parameters<typeof buildApiQueryString>[0],
): GeneratedApiPath {
  return path(`${base}${buildApiQueryString(values)}`);
}

/** Read-only endpoints Resume Builder uses to explain why create is blocked. */
export const resumeBuilderReadinessPaths = {
  evidence: withQuery("/api/v1/evidence", { limit: 100 }),
  experiences: withQuery("/api/v1/experiences", { includeProvenance: false }),
  skills: withQuery("/api/v1/skills", { includeProvenance: false }),
} as const;
