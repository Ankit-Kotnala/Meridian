import { serverApiFetch } from "@/shared/api/server-request";

export async function onboardingIsComplete(): Promise<boolean> {
  const response = await serverApiFetch("/api/v1/onboarding");
  if (!response.ok) {
    throw new Error(`Onboarding lookup failed with status ${response.status}.`);
  }
  const value: unknown = await response.json();
  return (
    typeof value === "object" &&
    value !== null &&
    "status" in value &&
    value.status === "completed"
  );
}
