import type { GeneratedApiPath } from "@/shared/api/api-path";
import { buildApiQueryString } from "@/shared/api/api-query-string";

function path(value: string): GeneratedApiPath {
  if (!value.startsWith("/api/v1/") || /[\s#]/.test(value)) {
    throw new Error("Invalid Application Workspace API path.");
  }
  return value as GeneratedApiPath;
}

function resource(base: string, id: string): GeneratedApiPath {
  if (!id) throw new Error("A resource identifier is required.");
  return path(`${base}/${encodeURIComponent(id)}`);
}

export const applicationPaths = {
  application: (id: string) => resource("/api/v1/applications", id),
  applicationProfile: path("/api/v1/application-profile"),
  applicationPacks: (id: string) =>
    path(`/api/v1/applications/${encodeURIComponent(id)}/application-packs`),
  applicationStage: (id: string) =>
    path(`/api/v1/applications/${encodeURIComponent(id)}/stage`),
  applicationTasks: (id: string) =>
    path(`/api/v1/applications/${encodeURIComponent(id)}/tasks`),
  applicationEvents: (id: string) =>
    path(`/api/v1/applications/${encodeURIComponent(id)}/events`),
  applicationNotes: (id: string) =>
    path(`/api/v1/applications/${encodeURIComponent(id)}/notes`),
  applications: path("/api/v1/applications"),
  calendar: path("/api/v1/applications/calendar"),
  applicationDocument: (applicationId: string, documentId: string) =>
    path(
      `/api/v1/applications/${encodeURIComponent(
        applicationId,
      )}/documents/${encodeURIComponent(documentId)}`,
    ),
  pack: (id: string) => resource("/api/v1/application-packs", id),
  packConsistency: (id: string) =>
    path(`/api/v1/application-packs/${encodeURIComponent(id)}/consistency`),
  applicationTask: (applicationId: string, taskId: string) =>
    path(
      `/api/v1/applications/${encodeURIComponent(
        applicationId,
      )}/tasks/${encodeURIComponent(taskId)}`,
    ),
  resumeVersions: (id: string) =>
    path(`/api/v1/resumes/${encodeURIComponent(id)}/versions`),
  resumes: path("/api/v1/resumes"),
  savedJobs: path("/api/v1/jobs"),
} as const;

export function withApplicationQuery(
  base: GeneratedApiPath,
  values: Parameters<typeof buildApiQueryString>[0],
): GeneratedApiPath {
  return path(`${base}${buildApiQueryString(values)}`);
}
