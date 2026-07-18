"use client";

import { apiMutation, apiQuery } from "@/shared/api/browser-request";

import { roleExplorerPaths, withQuery } from "./paths";
import type {
  RoleComparison,
  RolePage,
  RoleReadiness,
  RoleReadinessPage,
  RoleReadinessRequest,
  RoleSeniority,
  SavedRole,
  SavedRoleInput,
  SavedRolePage,
  SavedRoleUpdate,
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

export async function getRoles(filters: {
  domain?: string;
  industry?: string;
  limit?: number;
  q?: string;
  seniority?: RoleSeniority | "";
}): Promise<RolePage> {
  const response = await query(
    withQuery(roleExplorerPaths.roles, {
      domain: filters.domain || undefined,
      industry: filters.industry || undefined,
      limit: filters.limit,
      q: filters.q || undefined,
      seniority: filters.seniority || undefined,
    }),
  );
  return (await response.json()) as RolePage;
}

export async function getSavedRoles(): Promise<SavedRolePage> {
  return (await (
    await query(roleExplorerPaths.savedRoles)
  ).json()) as SavedRolePage;
}

export async function saveRole(input: SavedRoleInput): Promise<SavedRole> {
  const response = await mutate(roleExplorerPaths.savedRoles, {
    body: JSON.stringify(input),
    method: "POST",
  });
  return (await response.json()) as SavedRole;
}

export async function updateSavedRole(
  savedRole: SavedRole,
  input: SavedRoleUpdate,
): Promise<SavedRole> {
  const response = await mutate(roleExplorerPaths.savedRole(savedRole.id), {
    body: JSON.stringify(input),
    headers: headers(savedRole.version),
    method: "PATCH",
  });
  return (await response.json()) as SavedRole;
}

export async function deleteSavedRole(savedRole: SavedRole): Promise<void> {
  await mutate(roleExplorerPaths.savedRole(savedRole.id), {
    headers: headers(savedRole.version),
    method: "DELETE",
  });
}

export async function analyzeRole(
  input: RoleReadinessRequest,
): Promise<RoleReadiness> {
  const response = await mutate(roleExplorerPaths.readiness, {
    body: JSON.stringify(input),
    headers: headers(undefined, crypto.randomUUID()),
    method: "POST",
  });
  return (await response.json()) as RoleReadiness;
}

export async function getReadinessHistory(
  roleId?: string,
): Promise<RoleReadinessPage> {
  return (await (
    await query(
      withQuery(roleExplorerPaths.readiness, {
        roleId,
      }),
    )
  ).json()) as RoleReadinessPage;
}

export async function compareRoles(roleIds: string[]): Promise<RoleComparison> {
  return (await (
    await query(
      withQuery(roleExplorerPaths.compare, {
        roleId: roleIds,
      }),
    )
  ).json()) as RoleComparison;
}
