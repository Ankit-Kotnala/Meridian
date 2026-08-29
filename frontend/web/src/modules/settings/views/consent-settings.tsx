"use client";

import { RefreshCcw, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Button,
  Card,
  CheckboxField,
  ErrorState,
  LoadingSkeleton,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  getConsents,
  setConsent,
  type ConsentPurpose,
  type ConsentState,
} from "../api/settings-api";

const choices: ReadonlyArray<{
  description: string;
  label: string;
  purpose: ConsentPurpose;
}> = [
  {
    purpose: "modelTraining",
    label: "Allow model training with my content",
    description:
      "Off by default. Meridian does not use your content to train models unless you explicitly grant this purpose.",
  },
  {
    purpose: "productAnalytics",
    label: "Allow privacy-preserving product analytics",
    description:
      "Raw resumes, evidence text, and generated prose are excluded from analytics and logs.",
  },
  {
    purpose: "productEmail",
    label: "Allow optional product email",
    description:
      "Account security and transactional messages are separate from optional product communication.",
  },
];

export function ConsentSettings() {
  const [consents, setConsents] = useState<ConsentState[]>();
  const [failure, setFailure] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [busy, setBusy] = useState<ConsentPurpose>();

  const load = useCallback(async () => {
    try {
      const saved = await getConsents();
      setFailure(undefined);
      setConsents(saved);
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "We couldn’t load your consent choices."),
      );
    }
  }, []);
  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  function current(purpose: ConsentPurpose): ConsentState | undefined {
    return consents?.find((item) => item.purpose === purpose);
  }

  async function change(purpose: ConsentPurpose, granted: boolean) {
    setBusy(purpose);
    setFailure(undefined);
    setNotice(undefined);
    try {
      const saved = await setConsent(purpose, granted);
      setConsents((items) => [
        ...(items?.filter((item) => item.purpose !== purpose) ?? []),
        saved,
      ]);
      setNotice(
        `${choices.find((choice) => choice.purpose === purpose)?.label ?? "Consent"} updated.`,
      );
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "We couldn’t save that consent choice."),
      );
    } finally {
      setBusy(undefined);
    }
  }

  if (!consents && !failure) return <LoadingSkeleton variant="form" />;
  if (!consents)
    return (
      <ErrorState
        description={failure ?? "We couldn’t load your consent choices."}
        onRetry={load}
        title="Consent settings unavailable"
      />
    );

  return (
    <Card className="p-5 sm:p-7">
      <div className="flex items-start gap-3 border-b border-line pb-5">
        <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-success-soft text-success">
          <ShieldCheck aria-hidden="true" className="size-5" />
        </span>
        <div>
          <h2 className="text-lg font-extrabold text-foreground">
            Consent and data use
          </h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">
            Each decision is recorded as a versioned event. Withdrawing a
            purpose does not silently change another choice.
          </p>
        </div>
      </div>
      {failure && (
        <Alert className="mt-5" title="Consent choice not saved" tone="danger">
          {failure}
          <Button className="mt-3" onClick={load} variant="secondary">
            <RefreshCcw aria-hidden="true" className="size-4" /> Reload choices
          </Button>
        </Alert>
      )}
      {notice && <Alert className="mt-5" title={notice} tone="success" />}
      <div className="mt-5 space-y-4">
        {choices.map((choice) => {
          const saved = current(choice.purpose);
          return (
            <div key={choice.purpose}>
              <CheckboxField
                checked={saved?.granted ?? false}
                description={choice.description}
                disabled={busy === choice.purpose}
                id={`consent-${choice.purpose}`}
                label={choice.label}
                onChange={(event) =>
                  void change(choice.purpose, event.currentTarget.checked)
                }
              />
              <p className="mt-1 px-1 text-[0.7rem] leading-5 text-muted">
                {saved
                  ? `Recorded under policy ${saved.policyVersion}.`
                  : "No grant is recorded; this purpose remains off."}
              </p>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
