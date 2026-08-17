import type { GeneratedApiPath } from "@/shared/api/api-path";
import { buildApiQueryString } from "@/shared/api/api-query-string";

function path(value: string): GeneratedApiPath {
  if (!value.startsWith("/api/v1/") || /[\s#]/.test(value)) {
    throw new Error("Invalid workspace API path.");
  }
  return value as GeneratedApiPath;
}

function withQuery(
  base: string,
  values: Parameters<typeof buildApiQueryString>[0],
): GeneratedApiPath {
  return path(`${base}${buildApiQueryString(values)}`);
}

/**
 * Read-only endpoints the workspace home summarizes. The dashboard never writes
 * through these paths; each owning module keeps its own command surface.
 */
export const workspaceSummaryPaths = {
  achievements: withQuery("/api/v1/achievements", { limit: 100 }),
  applications: withQuery("/api/v1/applications", {
    limit: 100,
    sort: "updated_desc",
  }),
  dueReminders: withQuery("/api/v1/networking/reminders/due", { limit: 100 }),
  evidence: withQuery("/api/v1/evidence", { limit: 100 }),
  experiences: path("/api/v1/experiences"),
  skills: path("/api/v1/skills"),
} as const;
