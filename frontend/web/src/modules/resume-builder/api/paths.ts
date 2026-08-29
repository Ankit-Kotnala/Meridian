import type { GeneratedApiPath } from "@/shared/api/api-path";

function path(value: string): GeneratedApiPath {
  if (!value.startsWith("/api/v1/") || /[\s#]/.test(value)) {
    throw new Error("Invalid Resume Builder API path.");
  }
  return value as GeneratedApiPath;
}

function resource(base: string, id: string): GeneratedApiPath {
  if (!id) throw new Error("A resource identifier is required.");
  return path(`${base}/${encodeURIComponent(id)}`);
}

export const resumeBuilderPaths = {
  downloadIntent: (exportId: string) =>
    path(`/api/v1/exports/${encodeURIComponent(exportId)}/download-intent`),
  export: (exportId: string) => resource("/api/v1/exports", exportId),
  exportVerification: (exportId: string) =>
    path(`/api/v1/exports/${encodeURIComponent(exportId)}/verification`),
  resume: (resumeId: string) => resource("/api/v1/resumes", resumeId),
  resumeRestore: (resumeId: string, versionId: string) =>
    path(
      `/api/v1/resumes/${encodeURIComponent(resumeId)}/restore/` +
        encodeURIComponent(versionId),
    ),
  resumes: path("/api/v1/resumes"),
  resumeVersion: (versionId: string) =>
    resource("/api/v1/resume-versions", versionId),
  resumeVersionExport: (versionId: string) =>
    path(`/api/v1/resume-versions/${encodeURIComponent(versionId)}/export`),
  resumeVersions: (resumeId: string) =>
    path(`/api/v1/resumes/${encodeURIComponent(resumeId)}/versions`),
} as const;
