"use client";

import {
  ApiRequestError,
  apiMutation,
  apiQuery,
} from "@/shared/api/browser-request";

import { applicationPaths, withApplicationQuery } from "./paths";
import type {
  ApplicationCalendar,
  ApplicationConsistency,
  ApplicationCreateInput,
  ApplicationDetail,
  ApplicationEvent,
  ApplicationEventCreateInput,
  ApplicationEventPage,
  ApplicationNote,
  ApplicationNoteCreateInput,
  ApplicationNotePage,
  OutcomeStatus,
  ApplicationPack,
  ApplicationPackCreateInput,
  ApplicationPackPage,
  ApplicationPage,
  ApplicationSort,
  ApplicationStage,
  ApplicationStageUpdateInput,
  ApplicationTask,
  ApplicationTaskCreateInput,
  ApplicationTaskPage,
  ApplicationTaskUpdateInput,
  ApplicationUpdateInput,
  SavedJobPage,
  SavedResume,
  SavedResumeVersion,
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
  return apiMutation(path, init, { csrf: "session", retryAfterRefresh: true });
}

export async function listApplications(filters: {
  cursor?: string;
  limit?: number;
  q?: string;
  outcome?: OutcomeStatus | "";
  industry?: string;
  sort?: ApplicationSort;
  source?: string;
  stage?: ApplicationStage | "";
}): Promise<ApplicationPage> {
  const response = await query(
    withApplicationQuery(applicationPaths.applications, {
      cursor: filters.cursor,
      limit: filters.limit,
      industry: filters.industry || undefined,
      outcome: filters.outcome || undefined,
      q: filters.q || undefined,
      sort: filters.sort,
      source: filters.source || undefined,
      stage: filters.stage || undefined,
    }),
  );
  return (await response.json()) as ApplicationPage;
}

export async function listApplicationSourceJobs(
  options: { cursor?: string; limit?: number; q?: string } = {},
): Promise<SavedJobPage> {
  const response = await query(
    withApplicationQuery(applicationPaths.savedJobs, {
      cursor: options.cursor,
      limit: options.limit ?? 25,
      q: options.q || undefined,
    }),
  );
  return (await response.json()) as SavedJobPage;
}

export async function listApplicationSourceResumes(): Promise<SavedResume[]> {
  const response = await query(applicationPaths.resumes);
  const body = (await response.json()) as { items: SavedResume[] };
  return body.items;
}

export async function listApplicationSourceResumeVersions(
  resumeId: string,
): Promise<SavedResumeVersion[]> {
  const response = await query(applicationPaths.resumeVersions(resumeId));
  const body = (await response.json()) as { items: SavedResumeVersion[] };
  return body.items;
}

export async function getApplication(
  applicationId: string,
): Promise<ApplicationDetail> {
  const response = await query(applicationPaths.application(applicationId));
  return (await response.json()) as ApplicationDetail;
}

export async function createApplication(
  input: ApplicationCreateInput,
  idempotencyKey: string,
): Promise<ApplicationDetail> {
  const response = await mutate(applicationPaths.applications, {
    body: JSON.stringify(input),
    headers: headers(undefined, idempotencyKey),
    method: "POST",
  });
  return (await response.json()) as ApplicationDetail;
}

export async function updateApplication(
  application: Pick<ApplicationDetail, "id" | "version">,
  input: ApplicationUpdateInput,
): Promise<ApplicationDetail> {
  const response = await mutate(applicationPaths.application(application.id), {
    body: JSON.stringify(input),
    headers: headers(application.version),
    method: "PATCH",
  });
  return (await response.json()) as ApplicationDetail;
}

export async function updateApplicationStage(
  application: Pick<ApplicationDetail, "id" | "version">,
  input: ApplicationStageUpdateInput,
): Promise<ApplicationDetail> {
  const response = await mutate(
    applicationPaths.applicationStage(application.id),
    {
      body: JSON.stringify(input),
      headers: headers(application.version),
      method: "PATCH",
    },
  );
  return (await response.json()) as ApplicationDetail;
}

export async function deleteApplication(
  application: Pick<ApplicationDetail, "id" | "version">,
): Promise<void> {
  await mutate(applicationPaths.application(application.id), {
    headers: headers(application.version),
    method: "DELETE",
  });
}

export async function getApplicationCalendar(filters: {
  end: string;
  start: string;
}): Promise<ApplicationCalendar> {
  const response = await query(
    withApplicationQuery(applicationPaths.calendar, filters),
  );
  return (await response.json()) as ApplicationCalendar;
}

export async function listApplicationTasks(
  applicationId: string,
  options: { cursor?: string; limit?: number } = {},
): Promise<ApplicationTaskPage> {
  const response = await query(
    withApplicationQuery(applicationPaths.applicationTasks(applicationId), {
      cursor: options.cursor,
      limit: options.limit ?? 25,
    }),
  );
  return (await response.json()) as ApplicationTaskPage;
}

export async function createApplicationTask(
  applicationId: string,
  input: ApplicationTaskCreateInput,
  idempotencyKey: string,
): Promise<ApplicationTask> {
  const response = await mutate(
    applicationPaths.applicationTasks(applicationId),
    {
      body: JSON.stringify(input),
      headers: headers(undefined, idempotencyKey),
      method: "POST",
    },
  );
  return (await response.json()) as ApplicationTask;
}

export async function updateApplicationTask(
  applicationId: string,
  task: Pick<ApplicationTask, "id" | "version">,
  input: ApplicationTaskUpdateInput,
): Promise<ApplicationTask> {
  const response = await mutate(
    applicationPaths.applicationTask(applicationId, task.id),
    {
      body: JSON.stringify(input),
      headers: headers(task.version),
      method: "PATCH",
    },
  );
  return (await response.json()) as ApplicationTask;
}

export async function listApplicationNotes(
  applicationId: string,
  options: { cursor?: string; limit?: number } = {},
): Promise<ApplicationNotePage> {
  const response = await query(
    withApplicationQuery(applicationPaths.applicationNotes(applicationId), {
      cursor: options.cursor,
      limit: options.limit ?? 25,
    }),
  );
  return (await response.json()) as ApplicationNotePage;
}

export async function createApplicationNote(
  applicationId: string,
  input: ApplicationNoteCreateInput,
  idempotencyKey: string,
): Promise<ApplicationNote> {
  const response = await mutate(
    applicationPaths.applicationNotes(applicationId),
    {
      body: JSON.stringify(input),
      headers: headers(undefined, idempotencyKey),
      method: "POST",
    },
  );
  return (await response.json()) as ApplicationNote;
}

export async function listApplicationEvents(
  applicationId: string,
  options: { cursor?: string; limit?: number } = {},
): Promise<ApplicationEventPage> {
  const response = await query(
    withApplicationQuery(applicationPaths.applicationEvents(applicationId), {
      cursor: options.cursor,
      limit: options.limit ?? 50,
    }),
  );
  return (await response.json()) as ApplicationEventPage;
}

export async function createApplicationEvent(
  applicationId: string,
  input: ApplicationEventCreateInput,
  idempotencyKey: string,
): Promise<ApplicationEvent> {
  const response = await mutate(
    applicationPaths.applicationEvents(applicationId),
    {
      body: JSON.stringify(input),
      headers: headers(undefined, idempotencyKey),
      method: "POST",
    },
  );
  return (await response.json()) as ApplicationEvent;
}

export async function listApplicationPacks(
  applicationId: string,
  options: { cursor?: string; limit?: number } = {},
): Promise<ApplicationPackPage> {
  const response = await query(
    withApplicationQuery(applicationPaths.applicationPacks(applicationId), {
      cursor: options.cursor,
      limit: options.limit ?? 25,
    }),
  );
  return (await response.json()) as ApplicationPackPage;
}

export async function generateApplicationPack(
  applicationId: string,
  input: ApplicationPackCreateInput,
  idempotencyKey: string,
): Promise<ApplicationPack> {
  const response = await mutate(
    applicationPaths.applicationPacks(applicationId),
    {
      body: JSON.stringify(input),
      headers: headers(undefined, idempotencyKey),
      method: "POST",
    },
  );
  return (await response.json()) as ApplicationPack;
}

export async function getApplicationPack(
  packId: string,
): Promise<ApplicationPack> {
  const response = await query(applicationPaths.pack(packId));
  return (await response.json()) as ApplicationPack;
}

export async function getApplicationConsistency(
  packId: string,
): Promise<ApplicationConsistency> {
  const response = await query(applicationPaths.packConsistency(packId));
  return (await response.json()) as ApplicationConsistency;
}

export async function deleteApplicationDocument(
  applicationId: string,
  documentId: string,
): Promise<void> {
  await mutate(
    applicationPaths.applicationDocument(applicationId, documentId),
    { method: "DELETE" },
  );
}

export { ApiRequestError };
