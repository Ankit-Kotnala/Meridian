"use client";

import { ArrowRight, FileSearch, RefreshCcw, SearchCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  Alert,
  Button,
  Card,
  EmptyState,
  ErrorState,
  FieldLabel,
  LoadingSkeleton,
  Select,
  TextField,
  buttonStyles,
  cn,
} from "@careeros/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  getOnboarding,
  OnboardingRequestError,
  type OnboardingState,
  updateOnboarding,
} from "../api/onboarding-api";
import { OnboardingProgress } from "../components/onboarding-progress";

function addSkipped(
  state: OnboardingState,
  step: OnboardingState["currentStep"],
) {
  return Array.from(new Set([...state.skippedSteps, step]));
}

function handoffLabel(value: OnboardingState["resumeHandoff"]) {
  return {
    analysisReady: "Analysis ready",
    failed: "Processing failed",
    notStarted: "Not started",
    processing: "Processing",
    reviewRequired: "Review required",
    reviewed: "Reviewed",
    skipped: "Skipped",
  }[value];
}

export function OnboardingView() {
  const router = useRouter();
  const [state, setState] = useState<OnboardingState>();
  const [failure, setFailure] = useState<string>();
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const saved = await getOnboarding();
      setFailure(undefined);
      setState(saved);
    } catch (error) {
      setFailure(
        requestErrorMessage(
          error,
          "We couldn’t load your saved onboarding progress.",
        ),
      );
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  async function save(updates: Partial<OnboardingState>) {
    if (!state) return;
    setSaving(true);
    setFailure(undefined);
    try {
      const saved = await updateOnboarding(state, updates);
      setState(saved);
      if (saved.status === "completed") {
        router.replace("/dashboard");
        router.refresh();
      }
    } catch (error) {
      if (
        error instanceof OnboardingRequestError &&
        error.failure.status === 409
      ) {
        setFailure(
          "Your onboarding changed in another tab. Reload the latest saved version.",
        );
      } else {
        setFailure(
          requestErrorMessage(error, "We couldn’t save this onboarding step."),
        );
      }
    } finally {
      setSaving(false);
    }
  }

  if (!state && !failure) {
    return (
      <main className="mx-auto max-w-5xl p-4 sm:p-6 lg:p-8" id="main-content">
        <LoadingSkeleton />
      </main>
    );
  }
  if (!state) {
    return (
      <main className="mx-auto max-w-5xl p-4 sm:p-6 lg:p-8" id="main-content">
        <ErrorState
          description={
            failure ?? "We couldn’t load your saved onboarding progress."
          }
          onRetry={load}
          title="Onboarding unavailable"
        />
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-5xl p-4 sm:p-6 lg:p-8" id="main-content">
      <header className="mb-6">
        <p className="eyebrow">Account onboarding</p>
        <h1 className="mt-2 text-2xl font-black tracking-[-0.035em] text-foreground sm:text-3xl">
          Set up your CareerOS workspace
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
          Progress is saved after each step. Optional steps can be skipped and
          revisited without creating placeholder career data.
        </p>
      </header>
      <OnboardingProgress current={state.currentStep} />
      {failure && (
        <Alert
          className="mt-5"
          title="Your changes were not saved"
          tone="danger"
        >
          {failure}
          <Button className="mt-3" onClick={load} variant="secondary">
            <RefreshCcw aria-hidden="true" className="size-4" /> Reload saved
            progress
          </Button>
        </Alert>
      )}

      <Card className="mt-5 p-5 sm:p-7">
        {state.currentStep === "profile" && (
          <form
            className="space-y-5"
            onSubmit={(event: FormEvent<HTMLFormElement>) => {
              event.preventDefault();
              const displayName = String(
                new FormData(event.currentTarget).get("displayName") ?? "",
              ).trim();
              if (!displayName) {
                setFailure("Enter the name you want CareerOS to use.");
                return;
              }
              void save({ currentStep: "resume", displayName });
            }}
          >
            <div>
              <h2 className="text-lg font-extrabold text-foreground">
                Confirm your profile name
              </h2>
              <p className="mt-2 text-sm leading-6 text-muted">
                This is account presentation data, not a claim about your
                employment history.
              </p>
            </div>
            <TextField
              autoComplete="name"
              defaultValue={state.displayName}
              id="displayName"
              label="Name"
              maxLength={100}
              name="displayName"
              required
            />
            <Button
              loading={saving}
              loadingLabel="Saving profile…"
              type="submit"
            >
              Save and continue{" "}
              <ArrowRight aria-hidden="true" className="size-4" />
            </Button>
          </form>
        )}

        {state.currentStep === "resume" && (
          <EmptyState
            action={
              <div className="flex flex-col gap-3 sm:flex-row">
                <Link
                  className={cn(buttonStyles.base, buttonStyles.primary)}
                  href="/resume-health/account"
                >
                  Upload and review a resume
                  <ArrowRight aria-hidden="true" className="size-4" />
                </Link>
                <Button
                  loading={saving}
                  loadingLabel="Saving handoff…"
                  onClick={() =>
                    void save({
                      currentStep: "parsedReview",
                      skippedSteps: addSkipped(state, "resume"),
                    })
                  }
                  variant="secondary"
                >
                  Continue without a resume
                </Button>
              </div>
            }
            description="Secure PDF and DOCX admission, parsed-field review, and deterministic Resume Health are available in your protected workspace. This optional onboarding handoff remains skippable."
            title="Add a resume for review"
          />
        )}

        {state.currentStep === "parsedReview" && (
          <EmptyState
            action={
              <div className="flex flex-col gap-3 sm:flex-row">
                <Link
                  className={cn(buttonStyles.base, buttonStyles.primary)}
                  href="/resume-health/account"
                >
                  Open parsed resume review
                </Link>
                <Button
                  loading={saving}
                  loadingLabel="Saving handoff…"
                  onClick={() =>
                    void save({
                      currentStep: "preferences",
                      skippedSteps: addSkipped(state, "parsedReview"),
                    })
                  }
                  variant="secondary"
                >
                  Continue to preferences
                </Button>
              </div>
            }
            description="Resume Health owns the real parsed document and correction workflow. Onboarding does not infer completion or create placeholder facts; you may review there or explicitly skip this optional handoff."
            title="Review uncertain parsed information"
          />
        )}

        {state.currentStep === "preferences" && (
          <form
            className="space-y-5"
            onSubmit={(event: FormEvent<HTMLFormElement>) => {
              event.preventDefault();
              const form = new FormData(event.currentTarget);
              const optional = (name: string) =>
                String(form.get(name) ?? "").trim() || null;
              void save({
                currentStep: "complete",
                industry: optional("industry"),
                language: String(form.get("language") ?? "en").trim() || "en",
                preferredLocation: optional("preferredLocation"),
                seniority:
                  (optional("seniority") as OnboardingState["seniority"]) ??
                  null,
                targetRole: optional("targetRole"),
                workModel:
                  (optional("workModel") as OnboardingState["workModel"]) ??
                  null,
                writingStyle: String(
                  form.get("writingStyle") ?? "balanced",
                ) as OnboardingState["writingStyle"],
              });
            }}
          >
            <div>
              <h2 className="text-lg font-extrabold text-foreground">
                Choose working preferences
              </h2>
              <p className="mt-2 text-sm leading-6 text-muted">
                These values guide future filters and writing behavior. They are
                not career claims and can be changed later.
              </p>
            </div>
            <div className="grid gap-5 sm:grid-cols-2">
              <TextField
                defaultValue={state.targetRole ?? ""}
                id="targetRole"
                label="Target role (optional)"
                maxLength={160}
                name="targetRole"
              />
              <TextField
                defaultValue={state.preferredLocation ?? ""}
                id="preferredLocation"
                label="Preferred location (optional)"
                maxLength={160}
                name="preferredLocation"
              />
              <div className="space-y-2">
                <FieldLabel htmlFor="workModel">
                  Work model (optional)
                </FieldLabel>
                <Select
                  defaultValue={state.workModel ?? ""}
                  id="workModel"
                  name="workModel"
                >
                  <option value="">No preference</option>
                  <option value="onsite">On-site</option>
                  <option value="hybrid">Hybrid</option>
                  <option value="remote">Remote</option>
                  <option value="flexible">Flexible</option>
                </Select>
              </div>
              <div className="space-y-2">
                <FieldLabel htmlFor="seniority">
                  Seniority (optional)
                </FieldLabel>
                <Select
                  defaultValue={state.seniority ?? ""}
                  id="seniority"
                  name="seniority"
                >
                  <option value="">No preference</option>
                  <option value="entry">Entry</option>
                  <option value="mid">Mid-level</option>
                  <option value="senior">Senior</option>
                  <option value="lead">Lead</option>
                  <option value="executive">Executive</option>
                </Select>
              </div>
              <TextField
                defaultValue={state.industry ?? ""}
                id="industry"
                label="Industry (optional)"
                maxLength={120}
                name="industry"
              />
              <TextField
                defaultValue={state.language}
                id="language"
                label="Language"
                maxLength={35}
                name="language"
                required
              />
              <div className="space-y-2 sm:col-span-2">
                <FieldLabel htmlFor="writingStyle">
                  Writing preference
                </FieldLabel>
                <Select
                  defaultValue={state.writingStyle}
                  id="writingStyle"
                  name="writingStyle"
                >
                  <option value="concise">Concise</option>
                  <option value="balanced">Balanced</option>
                  <option value="detailed">Detailed</option>
                </Select>
              </div>
            </div>
            <Alert title="Optional means optional" tone="info">
              Leaving a preference blank will not be interpreted as a career
              fact or disadvantage.
            </Alert>
            <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <Button
                loading={saving}
                onClick={() =>
                  void save({
                    currentStep: "complete",
                    skippedSteps: addSkipped(state, "preferences"),
                  })
                }
                type="button"
                variant="secondary"
              >
                Skip optional preferences
              </Button>
              <Button
                loading={saving}
                loadingLabel="Finishing onboarding…"
                type="submit"
              >
                Finish onboarding{" "}
                <ArrowRight aria-hidden="true" className="size-4" />
              </Button>
            </div>
          </form>
        )}

        {state.currentStep === "complete" && (
          <EmptyState
            action={
              <Button onClick={() => router.push("/dashboard")}>
                Open dashboard{" "}
                <ArrowRight aria-hidden="true" className="size-4" />
              </Button>
            }
            description="Your profile and optional preferences are saved. No resume, parsed facts, or scores were created during this phase."
            title="Onboarding complete"
          />
        )}
      </Card>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <div className="flex items-start gap-3 rounded-xl border border-line bg-white p-4">
          <FileSearch
            aria-hidden="true"
            className="mt-0.5 size-5 text-primary"
          />
          <div>
            <p className="text-sm font-extrabold text-foreground">
              Resume handoff
            </p>
            <p className="mt-1 text-xs leading-5 text-muted">
              Status: {handoffLabel(state.resumeHandoff)}
            </p>
          </div>
        </div>
        <div className="flex items-start gap-3 rounded-xl border border-line bg-white p-4">
          <SearchCheck
            aria-hidden="true"
            className="mt-0.5 size-5 text-primary"
          />
          <div>
            <p className="text-sm font-extrabold text-foreground">
              Parsed review handoff
            </p>
            <p className="mt-1 text-xs leading-5 text-muted">
              Status: {handoffLabel(state.parsedReviewHandoff)}
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
