import type { GeneratedApiPath } from "@/shared/api/api-path";

function path(value: string): GeneratedApiPath {
  if (!value.startsWith("/api/v1/") || /[\s#]/.test(value)) {
    throw new Error("Invalid Change Studio API path.");
  }
  return value as GeneratedApiPath;
}

function resource(base: string, id: string): GeneratedApiPath {
  if (!id) throw new Error("A resource identifier is required.");
  return path(`${base}/${encodeURIComponent(id)}`);
}

export const changeStudioPaths = {
  answerClarification: (id: string) =>
    path(`/api/v1/clarifications/${encodeURIComponent(id)}/answer`),
  changeSet: (id: string) => resource("/api/v1/change-sets", id),
  changeSets: path("/api/v1/change-sets"),
  operationAccept: (changeSetId: string, operationId: string) =>
    path(
      `/api/v1/change-sets/${encodeURIComponent(changeSetId)}/operations/` +
        `${encodeURIComponent(operationId)}/accept`,
    ),
  operationAlternative: (changeSetId: string, operationId: string) =>
    path(
      `/api/v1/change-sets/${encodeURIComponent(changeSetId)}/operations/` +
        `${encodeURIComponent(operationId)}/alternatives`,
    ),
  operationEdit: (changeSetId: string, operationId: string) =>
    path(
      `/api/v1/change-sets/${encodeURIComponent(changeSetId)}/operations/` +
        `${encodeURIComponent(operationId)}/edit`,
    ),
  operationLock: (changeSetId: string, operationId: string) =>
    path(
      `/api/v1/change-sets/${encodeURIComponent(changeSetId)}/operations/` +
        `${encodeURIComponent(operationId)}/lock`,
    ),
  operationReject: (changeSetId: string, operationId: string) =>
    path(
      `/api/v1/change-sets/${encodeURIComponent(changeSetId)}/operations/` +
        `${encodeURIComponent(operationId)}/reject`,
    ),
  operationUnlock: (changeSetId: string, operationId: string) =>
    path(
      `/api/v1/change-sets/${encodeURIComponent(changeSetId)}/operations/` +
        `${encodeURIComponent(operationId)}/unlock`,
    ),
  safeApply: (id: string) =>
    path(`/api/v1/change-sets/${encodeURIComponent(id)}/apply-safe`),
  undo: (id: string) =>
    path(`/api/v1/change-sets/${encodeURIComponent(id)}/undo`),
  redo: (id: string) =>
    path(`/api/v1/change-sets/${encodeURIComponent(id)}/redo`),
  restoreVersion: (changeSetId: string, versionId: string) =>
    path(
      `/api/v1/change-sets/${encodeURIComponent(changeSetId)}/versions/` +
        `${encodeURIComponent(versionId)}/restore`,
    ),
} as const;
