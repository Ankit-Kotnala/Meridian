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

async function query(
  path: Parameters<typeof apiQuery>[0],
  signal?: AbortSignal,
) {
  return apiQuery(path, {
    retryAfterRefresh: true,
    ...(signal ? { signal } : {}),
  });
}

async function mutate(
  path: Parameters<typeof apiMutation>[0],
  init: Parameters<typeof apiMutation>[1],
) {
  return apiMutation(path, init, { csrf: "session", retryAfterRefresh: true });
}

export async function listResumes(): Promise<Resume[]> {
  const response = await query(resumeBuilderPaths.resumes);
  const body = (await response.json()) as { items?: Resume[] };
  return Array.isArray(body.items) ? body.items : [];
}

export async function getSourceOptions(
  cacheBust?: number,
): Promise<ResumeSourceOptions> {
  const path =
    cacheBust === undefined
      ? resumeBuilderPaths.sourceOptions
      : (`${resumeBuilderPaths.sourceOptions}?cacheBust=${cacheBust}` as typeof resumeBuilderPaths.sourceOptions);
  const response = await query(path);
  return (await response.json()) as ResumeSourceOptions;
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

export async function getExport(
  exportId: string,
  signal?: AbortSignal,
): Promise<ResumeExportRecord> {
  const response = await query(resumeBuilderPaths.export(exportId), signal);
  return (await response.json()) as ResumeExportRecord;
}

const processingExportStatuses: ReadonlySet<
  ResumeExportRecord["export"]["status"]
> = new Set(["pending", "rendering", "retry_wait"]);

function wait(delay: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(signal.reason);
      return;
    }
    const onAbort = () => {
      window.clearTimeout(timer);
      reject(signal?.reason);
    };
    const timer = window.setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, delay);
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

export async function waitForExportCompletion(
  initial: ResumeExportRecord,
  signal?: AbortSignal,
): Promise<ResumeExportRecord> {
  let record = initial;
  const deadline = Date.now() + 60_000;
  let pollCount = 0;
  while (processingExportStatuses.has(record.export.status)) {
    if (Date.now() >= deadline) {
      throw new Error("The export did not reach a terminal state in time.");
    }
    if (pollCount > 0) {
      await wait(Math.min(2_000, 500 + pollCount * 250), signal);
    }
    record = await getExport(record.export.id, signal);
    pollCount += 1;
  }
  return record;
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
