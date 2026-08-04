import { apiMutation, apiQuery } from "@/shared/api/browser-request";

export type PlanDTO = {
  tier: "free" | "sprint" | "pro" | "coach";
  name: string;
  description: string;
  max_resumes: number;
  max_change_sets_per_month: number;
  max_exports_per_month: number;
  ai_grounding_enabled: boolean;
  interview_prep_enabled: boolean;
  networking_enabled: boolean;
  analytics_enabled: boolean;
  monthly_price_usd: number;
  annual_price_usd: number;
};

export type SubscriptionDTO = {
  tier: "free" | "sprint" | "pro" | "coach";
  status: string;
  billing_cycle: "monthly" | "annual";
  current_period_start: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
  entitlements: PlanDTO;
  resumes_count: number;
  resumes_limit: number;
  change_sets_used: number;
  change_sets_limit: number;
  exports_used: number;
  exports_limit: number;
};

export async function getSubscription(): Promise<SubscriptionDTO> {
  const res = await apiQuery("/api/v1/billing/subscription", {
    retryAfterRefresh: true,
  });
  return (await res.json()) as SubscriptionDTO;
}

export async function getPlans(): Promise<{ plans: PlanDTO[] }> {
  const res = await apiQuery("/api/v1/billing/plans", { retryAfterRefresh: true });
  return (await res.json()) as { plans: PlanDTO[] };
}

export async function createCheckoutSession(
  tier: "sprint" | "pro" | "coach",
  billingCycle: "monthly" | "annual" = "monthly",
): Promise<{ checkout_url: string; session_id: string }> {
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const res = await apiMutation(
    "/api/v1/billing/checkout",
    {
      method: "POST",
      body: JSON.stringify({
        tier,
        billing_cycle: billingCycle,
        success_url: `${origin}/settings/billing?status=success`,
        cancel_url: `${origin}/settings/billing?status=canceled`,
      }),
    },
    { csrf: "session", retryAfterRefresh: true },
  );
  return (await res.json()) as { checkout_url: string; session_id: string };
}

export async function createPortalSession(): Promise<{ portal_url: string }> {
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const res = await apiMutation(
    "/api/v1/billing/portal",
    {
      method: "POST",
      body: JSON.stringify({
        return_url: `${origin}/settings/billing`,
      }),
    },
    { csrf: "session", retryAfterRefresh: true },
  );
  return (await res.json()) as { portal_url: string };
}
