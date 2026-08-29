import type { components } from "@rezumi/contracts";

import { apiMutation, apiQuery } from "@/shared/api/browser-request";

export type PlanDTO = components["schemas"]["PlanResponse"];
export type SubscriptionDTO =
  components["schemas"]["SubscriptionSummaryResponse"];
type PlanListResponse = components["schemas"]["PlanListResponse"];
type CheckoutSessionResponse = components["schemas"]["CheckoutSessionResponse"];
type PortalSessionResponse = components["schemas"]["PortalSessionResponse"];

export async function getSubscription(): Promise<SubscriptionDTO> {
  const res = await apiQuery("/api/v1/billing/subscription", {
    retryAfterRefresh: true,
  });
  return (await res.json()) as SubscriptionDTO;
}

export async function getPlans(): Promise<PlanListResponse> {
  const res = await apiQuery("/api/v1/billing/plans", {
    retryAfterRefresh: true,
  });
  return (await res.json()) as PlanListResponse;
}

export async function createCheckoutSession(
  tier: "sprint" | "pro" | "coach",
  billingCycle: "monthly" | "annual" = "monthly",
): Promise<CheckoutSessionResponse> {
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const body: components["schemas"]["CheckoutSessionRequest"] = {
    tier,
    billingCycle,
    successUrl: `${origin}/settings/billing?status=success`,
    cancelUrl: `${origin}/settings/billing?status=canceled`,
  };
  const res = await apiMutation(
    "/api/v1/billing/checkout",
    { method: "POST", body: JSON.stringify(body) },
    { csrf: "session", retryAfterRefresh: true },
  );
  return (await res.json()) as CheckoutSessionResponse;
}

export async function createPortalSession(): Promise<PortalSessionResponse> {
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const body: components["schemas"]["PortalSessionRequest"] = {
    returnUrl: `${origin}/settings/billing`,
  };
  const res = await apiMutation(
    "/api/v1/billing/portal",
    { method: "POST", body: JSON.stringify(body) },
    { csrf: "session", retryAfterRefresh: true },
  );
  return (await res.json()) as PortalSessionResponse;
}
