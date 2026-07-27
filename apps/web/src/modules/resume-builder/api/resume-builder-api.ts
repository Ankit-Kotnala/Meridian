"use client";

import { apiMutation, apiQuery } from "@/shared/api/browser-request";

import { resumeBuilderPaths } from "./paths";
import type {
  Resume,
  ResumeCreateInput,
  ResumeDownloadIntent,
  ResumeExportInput,
  ResumeExportRecord,
  ResumeSourceOptions,
  ResumeUpdateInput,
  ResumeVersion,
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

export async function listResumes(): Promise<Resume[]> {
  const response = await query(resumeBuilderPaths.resumes);
  const body = (await response.json()) as { items: Resume[] };
  return body.items;
}

export async function createResume(input: ResumeCreateInput): Promise<Resume> {
  const response = await mutate(resumeBuilderPaths.resumes, {
    body: JSON.stringify(input),
    headers: headers(undefined, crypto.randomUUID()),
    method: "POST",
  });
  return (await response.json()) as Resume;
}

export async function updateResume(
  resume: Resume,
  input: ResumeUpdateInput,
): Promise<Resume> {
  const response = await mutate(resumeBuilderPaths.resume(resume.id), {
    body: JSON.stringify(input),
    headers: headers(resume.version, crypto.randomUUID()),
    method: "PATCH",
  });
  return (await response.json()) as Resume;
}

export async function listVersions(resumeId: string): Promise<ResumeVersion[]> {
  const response = await query(resumeBuilderPaths.resumeVersions(resumeId));
  const body = (await response.json()) as { items: ResumeVersion[] };
  return body.items;
}

export async function getResumeSourceOptions(
  resumeId: string,
): Promise<ResumeSourceOptions> {
  const response = await query(
    resumeBuilderPaths.resumeSourceOptions(resumeId),
  );
  return (await response.json()) as ResumeSourceOptions;
}

export async function createVersion(resume: Resume): Promise<ResumeVersion> {
  const response = await mutate(resumeBuilderPaths.resumeVersions(resume.id), {
    headers: headers(resume.version, crypto.randomUUID()),
    method: "POST",
  });
  return (await response.json()) as ResumeVersion;
}

export async function restoreVersion(
  resume: Resume,
  versionId: string,
): Promise<Resume> {
  const response = await mutate(
    resumeBuilderPaths.resumeRestore(resume.id, versionId),
    {
      headers: headers(resume.version, crypto.randomUUID()),
      method: "POST",
    },
  );
  return (await response.json()) as Resume;
}

export async function exportVersion(
  versionId: string,
  input: ResumeExportInput,
): Promise<ResumeExportRecord> {
  const response = await mutate(
    resumeBuilderPaths.resumeVersionExport(versionId),
    {
      body: JSON.stringify(input),
      headers: headers(undefined, crypto.randomUUID()),
      method: "POST",
    },
  );
  return (await response.json()) as ResumeExportRecord;
}

export async function getExport(exportId: string): Promise<ResumeExportRecord> {
  const response = await query(resumeBuilderPaths.export(exportId));
  return (await response.json()) as ResumeExportRecord;
}

export async function createDownloadIntent(
  exportId: string,
): Promise<ResumeDownloadIntent> {
  const response = await mutate(resumeBuilderPaths.downloadIntent(exportId), {
    headers: headers(undefined, crypto.randomUUID()),
    method: "POST",
  });
  return (await response.json()) as ResumeDownloadIntent;
}

export async function deleteExport(
  exportId: string,
): Promise<ResumeExportRecord> {
  const response = await mutate(resumeBuilderPaths.export(exportId), {
    headers: headers(undefined, crypto.randomUUID()),
    method: "DELETE",
  });
  return (await response.json()) as ResumeExportRecord;
}
