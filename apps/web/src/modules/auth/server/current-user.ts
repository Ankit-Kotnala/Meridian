import { redirect } from "next/navigation";

import type { components } from "@careeros/contracts";

import { serverApiFetch } from "@/shared/api/server-request";

export type CurrentUserView = Pick<
  components["schemas"]["MeResponse"],
  "displayName" | "email" | "emailVerified" | "version"
>;

function currentUser(value: unknown): CurrentUserView | undefined {
  if (typeof value !== "object" || value === null) return undefined;
  const candidate = value as Record<string, unknown>;
  if (
    typeof candidate.displayName !== "string" ||
    typeof candidate.email !== "string" ||
    typeof candidate.emailVerified !== "boolean" ||
    typeof candidate.version !== "number"
  ) {
    return undefined;
  }
  return {
    displayName: candidate.displayName,
    email: candidate.email,
    emailVerified: candidate.emailVerified,
    version: candidate.version,
  };
}

export async function getCurrentUser(): Promise<CurrentUserView | null> {
  const response = await serverApiFetch("/api/v1/me");
  if (response.status === 401 || response.status === 403) return null;
  if (!response.ok)
    throw new Error(
      `Current user lookup failed with status ${response.status}.`,
    );
  const parsed = currentUser(await response.json());
  if (!parsed)
    throw new Error("Current user response did not match the API contract.");
  return parsed;
}

export async function requireCurrentUser(
  returnTo: string,
): Promise<CurrentUserView> {
  const user = await getCurrentUser();
  if (!user) redirect(`/login?returnTo=${encodeURIComponent(returnTo)}`);
  if (!user.emailVerified) redirect("/verify-email");
  return user;
}
