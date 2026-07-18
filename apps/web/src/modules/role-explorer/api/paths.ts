import type { GeneratedApiPath } from "@/shared/api/api-path";
import { buildApiQueryString } from "@/shared/api/api-query-string";

function path(value: string): GeneratedApiPath {
  if (!value.startsWith("/api/v1/") || /[\s#]/.test(value)) {
    throw new Error("Invalid Role Explorer API path.");
  }
  return value as GeneratedApiPath;
}

function resource(base: string, id: string): GeneratedApiPath {
  if (!id) throw new Error("A resource identifier is required.");
  return path(`${base}/${encodeURIComponent(id)}`);
}

export const roleExplorerPaths = {
  analysis: (id: string) => resource("/api/v1/role-readiness", id),
  compare: path("/api/v1/role-readiness/compare"),
  readiness: path("/api/v1/role-readiness"),
  role: (id: string) => resource("/api/v1/roles", id),
  roles: path("/api/v1/roles"),
  savedRole: (id: string) => resource("/api/v1/saved-roles", id),
  savedRoles: path("/api/v1/saved-roles"),
} as const;

export function withQuery(
  base: GeneratedApiPath,
  values: Parameters<typeof buildApiQueryString>[0],
): GeneratedApiPath {
  return path(`${base}${buildApiQueryString(values)}`);
}
