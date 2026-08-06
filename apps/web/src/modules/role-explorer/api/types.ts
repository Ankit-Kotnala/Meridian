import type { components } from "@rezumi/contracts";

export type Role = components["schemas"]["RoleResponse"];
export type RolePage = components["schemas"]["RolePageResponse"];
export type SavedRole = components["schemas"]["SavedRoleResponse"];
export type SavedRolePage = components["schemas"]["SavedRolePageResponse"];
export type RoleReadiness = components["schemas"]["RoleReadinessResponse"];
export type RoleReadinessPage =
  components["schemas"]["RoleReadinessPageResponse"];
export type RoleComparison = components["schemas"]["RoleComparisonResponse"];
export type RoleSeniority = NonNullable<Role["seniority"]>;
export type SavedRoleInput = components["schemas"]["SavedRoleCreateRequest"];
export type SavedRoleUpdate = components["schemas"]["SavedRoleUpdateRequest"];
export type RoleReadinessRequest =
  components["schemas"]["RoleReadinessRequest"];
