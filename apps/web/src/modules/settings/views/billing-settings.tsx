"use client";

import { Check, CreditCard, ExternalLink } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingSkeleton,
} from "@careeros/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  createCheckoutSession,
  createPortalSession,
  getPlans,
  getSubscription,
  type PlanDTO,
  type SubscriptionDTO,
} from "../api/billing-api";
import { useSettingsCapabilities } from "../components/settings-capabilities-context";

export function BillingSettings() {
  const { capabilities, failure: capabilitiesFailure, loading: capabilitiesLoading } =
    useSettingsCapabilities();
  const [subscription, setSubscription] = useState<SubscriptionDTO>();
  const [plans, setPlans] = useState<PlanDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState<string>();
  const [actionBusy, setActionBusy] = useState<string>();
  const [cycle, setCycle] = useState<"monthly" | "annual">("monthly");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [subData, plansData] = await Promise.all([
        getSubscription(),
        getPlans(),
      ]);
      setSubscription(subData);
      setPlans(plansData.plans);
      setFailure(undefined);
    } catch (error) {
      setFailure(
        requestErrorMessage(
          error,
          "We couldn’t load your subscription and plans.",
        ),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!capabilities?.billingAvailable) return;
    queueMicrotask(() => void loadData());
  }, [capabilities?.billingAvailable, loadData]);

  if (capabilitiesLoading && !capabilities) {
    return <LoadingSkeleton variant="form" />;
  }

  if (!capabilities?.billingAvailable) {
    return (
      <EmptyState
        description={
          capabilitiesFailure ??
          "Billing and subscription management are not enabled in this environment."
        }
        title="Billing unavailable"
      />
    );
  }

  const handleCheckout = async (tier: "sprint" | "pro" | "coach") => {
    setActionBusy(tier);
    try {
      const res = await createCheckoutSession(tier, cycle);
      if (res.checkout_url) {
        window.location.assign(res.checkout_url);
      }
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "Failed to start checkout session."),
      );
    } finally {
      setActionBusy(undefined);
    }
  };

  const handlePortal = async () => {
    setActionBusy("portal");
    try {
      const res = await createPortalSession();
      if (res.portal_url) {
        window.location.assign(res.portal_url);
      }
    } catch (error) {
      setFailure(requestErrorMessage(error, "Failed to open customer portal."));
    } finally {
      setActionBusy(undefined);
    }
  };

  if (loading && !subscription) return <LoadingSkeleton variant="form" />;
  if (failure && !subscription)
    return (
      <ErrorState
        description={failure}
        onRetry={loadData}
        title="Billing settings unavailable"
      />
    );

  const currentTier = subscription?.tier ?? "free";

  return (
    <div className="flex flex-col gap-6">
      <Card className="p-5 sm:p-7">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-slate-100 text-muted">
              <CreditCard aria-hidden="true" className="size-5" />
            </span>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-extrabold text-foreground">
                  Current Subscription
                </h2>
                <Badge tone={currentTier === "free" ? "neutral" : "success"}>
                  {subscription?.entitlements.name ?? "Free"} Plan (
                  {subscription?.status ?? "active"})
                </Badge>
              </div>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">
                Your plan dictates workspace quotas for tailored AI change sets,
                exports, and team capabilities.
              </p>
            </div>
          </div>

          <Button
            loading={actionBusy === "portal"}
            onClick={handlePortal}
            variant="secondary"
          >
            Manage Billing <ExternalLink className="ml-2 size-4" />
          </Button>
        </div>

        {/* Quota Progress Bars */}
        {subscription && (
          <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4">
              <div className="flex justify-between text-xs font-semibold text-slate-600">
                <span>Resumes</span>
                <span>
                  {subscription.resumes_count} / {subscription.resumes_limit}
                </span>
              </div>
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-200">
                <div
                  className="h-full bg-emerald-500 transition-all"
                  style={{
                    width: `${Math.min(100, (subscription.resumes_count / subscription.resumes_limit) * 100)}%`,
                  }}
                />
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4">
              <div className="flex justify-between text-xs font-semibold text-slate-600">
                <span>Monthly AI Change Sets</span>
                <span>
                  {subscription.change_sets_used} /{" "}
                  {subscription.change_sets_limit}
                </span>
              </div>
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-200">
                <div
                  className="h-full bg-blue-500 transition-all"
                  style={{
                    width: `${Math.min(100, (subscription.change_sets_used / subscription.change_sets_limit) * 100)}%`,
                  }}
                />
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4">
              <div className="flex justify-between text-xs font-semibold text-slate-600">
                <span>Monthly Exports</span>
                <span>
                  {subscription.exports_used} / {subscription.exports_limit}
                </span>
              </div>
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-200">
                <div
                  className="h-full bg-indigo-500 transition-all"
                  style={{
                    width: `${Math.min(100, (subscription.exports_used / subscription.exports_limit) * 100)}%`,
                  }}
                />
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* Plan Tier Options */}
      <Card className="p-5 sm:p-7">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-lg font-bold text-foreground">
              Available Plans
            </h3>
            <p className="text-sm text-muted">
              Select the right plan for your career growth goals.
            </p>
          </div>
          <div className="mt-3 flex items-center rounded-lg border border-slate-200 p-1 sm:mt-0">
            <button
              className={`px-3 py-1 text-xs font-medium rounded-md transition ${
                cycle === "monthly"
                  ? "bg-slate-900 text-white"
                  : "text-slate-600"
              }`}
              onClick={() => setCycle("monthly")}
              type="button"
            >
              Monthly
            </button>
            <button
              className={`px-3 py-1 text-xs font-medium rounded-md transition ${
                cycle === "annual"
                  ? "bg-slate-900 text-white"
                  : "text-slate-600"
              }`}
              onClick={() => setCycle("annual")}
              type="button"
            >
              Annual (Save 20%)
            </button>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-4">
          {plans.map((plan) => {
            const isCurrent = plan.tier === currentTier;
            const price =
              cycle === "annual"
                ? plan.annual_price_usd / 12
                : plan.monthly_price_usd;

            return (
              <div
                className={`flex flex-col justify-between rounded-xl border p-5 transition ${
                  isCurrent
                    ? "border-emerald-500 bg-emerald-50/10 shadow-sm"
                    : "border-slate-200 hover:border-slate-300"
                }`}
                key={plan.tier}
              >
                <div>
                  <div className="flex items-center justify-between">
                    <h4 className="text-base font-bold text-foreground">
                      {plan.name}
                    </h4>
                    {isCurrent && <Badge tone="success">Active</Badge>}
                  </div>
                  <p className="mt-2 text-2xl font-black text-foreground">
                    ${price.toFixed(0)}{" "}
                    <span className="text-xs font-normal text-muted">/mo</span>
                  </p>
                  <p className="mt-2 text-xs leading-5 text-muted">
                    {plan.description}
                  </p>

                  <ul className="mt-4 flex flex-col gap-2 text-xs text-slate-700">
                    <li className="flex items-center gap-2">
                      <Check className="size-3.5 text-emerald-600" />
                      <span>
                        Up to <strong>{plan.max_resumes}</strong> Resumes
                      </span>
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="size-3.5 text-emerald-600" />
                      <span>
                        <strong>{plan.max_change_sets_per_month}</strong> AI
                        Change Sets/mo
                      </span>
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="size-3.5 text-emerald-600" />
                      <span>
                        <strong>{plan.max_exports_per_month}</strong> Verified
                        Exports/mo
                      </span>
                    </li>
                    {plan.interview_prep_enabled && (
                      <li className="flex items-center gap-2">
                        <Check className="size-3.5 text-emerald-600" />
                        <span>Interview Defense Map</span>
                      </li>
                    )}
                    {plan.analytics_enabled && (
                      <li className="flex items-center gap-2">
                        <Check className="size-3.5 text-emerald-600" />
                        <span>Full Career Analytics</span>
                      </li>
                    )}
                  </ul>
                </div>

                <div className="mt-6">
                  {isCurrent ? (
                    <Button className="w-full" disabled variant="secondary">
                      Current Plan
                    </Button>
                  ) : plan.tier === "free" ? (
                    <Button className="w-full" disabled variant="secondary">
                      Default Free
                    </Button>
                  ) : (
                    <Button
                      className="w-full"
                      loading={actionBusy === plan.tier}
                      onClick={() =>
                        handleCheckout(plan.tier as "sprint" | "pro" | "coach")
                      }
                    >
                      Upgrade to {plan.name}
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
