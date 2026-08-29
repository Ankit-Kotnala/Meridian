"use client";

import { apiMutation, apiQuery } from "@/shared/api/browser-request";

import { changeStudioPaths } from "./paths";
import type {
  ChangeSet,
  ChangeSetCreateInput,
  ClarificationAnswerInput,
  OperationAlternativeInput,
  OperationEditInput,
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

export async function createChangeSet(
  input: ChangeSetCreateInput,
): Promise<ChangeSet> {
  const response = await mutate(changeStudioPaths.changeSets, {
    body: JSON.stringify(input),
    headers: headers(undefined, crypto.randomUUID()),
    method: "POST",
  });
  return (await response.json()) as ChangeSet;
}

export async function getChangeSet(id: string): Promise<ChangeSet> {
  return (await (
    await query(changeStudioPaths.changeSet(id))
  ).json()) as ChangeSet;
}

export async function acceptOperation(
  changeSet: ChangeSet,
  operationId: string,
): Promise<ChangeSet> {
  const response = await mutate(
    changeStudioPaths.operationAccept(changeSet.id, operationId),
    {
      headers: headers(changeSet.version, crypto.randomUUID()),
      method: "POST",
    },
  );
  return (await response.json()) as ChangeSet;
}

export async function rejectOperation(
  changeSet: ChangeSet,
  operationId: string,
): Promise<ChangeSet> {
  const response = await mutate(
    changeStudioPaths.operationReject(changeSet.id, operationId),
    {
      headers: headers(changeSet.version, crypto.randomUUID()),
      method: "POST",
    },
  );
  return (await response.json()) as ChangeSet;
}

export async function editOperation(
  changeSet: ChangeSet,
  operationId: string,
  input: OperationEditInput,
): Promise<ChangeSet> {
  const response = await mutate(
    changeStudioPaths.operationEdit(changeSet.id, operationId),
    {
      body: JSON.stringify(input),
      headers: headers(changeSet.version, crypto.randomUUID()),
      method: "POST",
    },
  );
  return (await response.json()) as ChangeSet;
}

export async function createAlternative(
  changeSet: ChangeSet,
  operationId: string,
  input: OperationAlternativeInput,
): Promise<ChangeSet> {
  const response = await mutate(
    changeStudioPaths.operationAlternative(changeSet.id, operationId),
    {
      body: JSON.stringify(input),
      headers: headers(changeSet.version, crypto.randomUUID()),
      method: "POST",
    },
  );
  return (await response.json()) as ChangeSet;
}

export async function setOperationLocked(
  changeSet: ChangeSet,
  operationId: string,
  locked: boolean,
): Promise<ChangeSet> {
  const response = await mutate(
    locked
      ? changeStudioPaths.operationLock(changeSet.id, operationId)
      : changeStudioPaths.operationUnlock(changeSet.id, operationId),
    {
      headers: headers(changeSet.version, crypto.randomUUID()),
      method: "POST",
    },
  );
  return (await response.json()) as ChangeSet;
}

export async function applySafeChanges(
  changeSet: ChangeSet,
): Promise<ChangeSet> {
  const response = await mutate(changeStudioPaths.safeApply(changeSet.id), {
    headers: headers(changeSet.version, crypto.randomUUID()),
    method: "POST",
  });
  return (await response.json()) as ChangeSet;
}

export async function undoChangeSet(changeSet: ChangeSet): Promise<ChangeSet> {
  const response = await mutate(changeStudioPaths.undo(changeSet.id), {
    headers: headers(changeSet.version, crypto.randomUUID()),
    method: "POST",
  });
  return (await response.json()) as ChangeSet;
}

export async function redoChangeSet(changeSet: ChangeSet): Promise<ChangeSet> {
  const response = await mutate(changeStudioPaths.redo(changeSet.id), {
    headers: headers(changeSet.version, crypto.randomUUID()),
    method: "POST",
  });
  return (await response.json()) as ChangeSet;
}

export async function restoreVersion(
  changeSet: ChangeSet,
  versionId: string,
): Promise<ChangeSet> {
  const response = await mutate(
    changeStudioPaths.restoreVersion(changeSet.id, versionId),
    {
      headers: headers(changeSet.version, crypto.randomUUID()),
      method: "POST",
    },
  );
  return (await response.json()) as ChangeSet;
}

export async function answerClarification(
  changeSet: ChangeSet,
  clarificationId: string,
  input: ClarificationAnswerInput,
): Promise<ChangeSet> {
  const response = await mutate(
    changeStudioPaths.answerClarification(clarificationId),
    {
      body: JSON.stringify(input),
      headers: headers(changeSet.version, crypto.randomUUID()),
      method: "POST",
    },
  );
  return (await response.json()) as ChangeSet;
}
