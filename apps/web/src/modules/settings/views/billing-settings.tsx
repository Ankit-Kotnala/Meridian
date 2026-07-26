"use client";

import { CreditCard } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  ErrorState,
  LoadingSkeleton,
} from "@careeros/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  getSettingsCapabilities,
  type SettingsCapabilities,
} from "../api/settings-api";

export function BillingSettings() {
  const [capabilities, setCapabilities] = useState<SettingsCapabilities>();
  const [failure, setFailure] = useState<string>();

  const load = useCallback(async () => {
    try {
      setCapabilities(await getSettingsCapabilities());
      setFailure(undefined);
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "We couldn’t load billing capabilities."),
      );
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  if (!capabilities && !failure) return <LoadingSkeleton />;
  if (!capabilities)
    return (
      <ErrorState
        description={failure ?? "We couldn’t load billing capabilities."}
        onRetry={load}
        title="Billing settings unavailable"
      />
    );

  return (
    <Card className="p-5 sm:p-7">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-slate-100 text-muted">
            <CreditCard aria-hidden="true" className="size-5" />
          </span>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-extrabold text-foreground">
                Plan and billing
              </h2>
              <Badge tone="neutral">
                {capabilities.billingAvailable ? "Available" : "Not configured"}
              </Badge>
            </div>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">
              Prices, quotas, plan entitlements, and a billing provider require
              product-owner decisions. No plan or subscription is inferred from
              the frontend.
            </p>
          </div>
        </div>
        <Button disabled={!capabilities.billingAvailable}>
          Manage subscription
        </Button>
      </div>
      {!capabilities.billingAvailable && (
        <Alert className="mt-5" title="Billing is unavailable" tone="warning">
          The server reports no configured billing provider. Checkout, portal,
          subscription, and payment controls stay disabled.
        </Alert>
      )}
    </Card>
  );
}
