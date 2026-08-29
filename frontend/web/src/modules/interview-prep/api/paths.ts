import type { GeneratedApiPath } from "@/shared/api/api-path";
import { buildApiQueryString } from "@/shared/api/api-query-string";

function path(value: string): GeneratedApiPath {
  if (!value.startsWith("/api/v1/") || /[\s#]/.test(value)) {
    throw new Error("Invalid Interview Prep API path.");
  }
  return value as GeneratedApiPath;
}

function resource(base: string, id: string): GeneratedApiPath {
  if (!id) throw new Error("A resource identifier is required.");
  return path(`${base}/${encodeURIComponent(id)}`);
}

export const interviewPrepPaths = {
  applications: path("/api/v1/applications"),
  defenseMap: (applicationId: string) =>
    path(
      `/api/v1/interview-prep/applications/${encodeURIComponent(
        applicationId,
      )}/defense-map`,
    ),
  followUpDrafts: (sessionId: string) =>
    path(
      `/api/v1/interview-prep/sessions/${encodeURIComponent(
        sessionId,
      )}/follow-up-drafts`,
    ),
  followUpGenerate: (sessionId: string) =>
    path(
      `/api/v1/interview-prep/sessions/${encodeURIComponent(
        sessionId,
      )}/follow-up-drafts/generate`,
    ),
  note: (sessionId: string, noteId: string) =>
    path(
      `/api/v1/interview-prep/sessions/${encodeURIComponent(
        sessionId,
      )}/notes/${encodeURIComponent(noteId)}`,
    ),
  notes: (sessionId: string) =>
    path(
      `/api/v1/interview-prep/sessions/${encodeURIComponent(sessionId)}/notes`,
    ),
  questionGenerate: (sessionId: string) =>
    path(
      `/api/v1/interview-prep/sessions/${encodeURIComponent(
        sessionId,
      )}/questions/generate`,
    ),
  questions: (sessionId: string) =>
    path(
      `/api/v1/interview-prep/sessions/${encodeURIComponent(
        sessionId,
      )}/questions`,
    ),
  session: (sessionId: string) =>
    resource("/api/v1/interview-prep/sessions", sessionId),
  sessions: path("/api/v1/interview-prep/sessions"),
  stories: path("/api/v1/interview-prep/stories"),
  story: (storyId: string) =>
    resource("/api/v1/interview-prep/stories", storyId),
} as const;

export function withInterviewQuery(
  base: GeneratedApiPath,
  values: Parameters<typeof buildApiQueryString>[0],
): GeneratedApiPath {
  return path(`${base}${buildApiQueryString(values)}`);
}
