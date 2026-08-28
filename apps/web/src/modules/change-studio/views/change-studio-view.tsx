"use client";

import {
  AlertTriangle,
  Check,
  History,
  Lock,
  MessageSquare,
  Pencil,
  Redo2,
  RotateCcw,
  ShieldCheck,
  Undo2,
  Unlock,
  X,
  FileDiff,
} from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useMemo, useState, type FormEvent } from "react";

import {
  Alert,
  Badge,
  Button,
  EmptyState,
  ErrorState,
  FieldLabel,
  Input,
  LoadingSkeleton,
  PageHeader,
  cn,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  acceptOperation,
  answerClarification,
  applySafeChanges,
  createAlternative,
  createChangeSet,
  editOperation,
  getChangeSet,
  redoChangeSet,
  rejectOperation,
  restoreVersion,
  setOperationLocked,
  undoChangeSet,
} from "../api/change-studio-api";
import type { ChangeOperation, ChangeSet } from "../api/types";

function humanize(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function groundingTone(status: string) {
  if (status === "grounded") return "success" as const;
  if (status === "needs_clarification") return "warning" as const;
  return "danger" as const;
}

function statusTone(status: string) {
  if (status === "accepted") return "success" as const;
  if (status === "blocked") return "danger" as const;
  if (status === "rejected") return "neutral" as const;
  return "primary" as const;
}

export function ChangeStudioView() {
  const params = useSearchParams();
  const [analysisId, setAnalysisId] = useState(
    () => params.get("analysisId") ?? "",
  );
  const [existingId, setExistingId] = useState("");
  const [changeSet, setChangeSet] = useState<ChangeSet>();
  const [failure, setFailure] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const [busyKey, setBusyKey] = useState<string>();
  const [editingId, setEditingId] = useState<string>();
  const [draftText, setDraftText] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const currentVersion = useMemo(
    () =>
      changeSet?.versions.find(
        (version) => version.id === changeSet.currentVersionId,
      ) ?? changeSet?.currentVersion,
    [changeSet],
  );

  async function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = analysisId.trim();
    setBusyKey("generate");
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const next = await createChangeSet({
        analysisId: normalized,
        length: "standard",
        maxOperations: 5,
        targetKind: "tailored_resume_bullet",
        tone: "direct",
      });
      setChangeSet(next);
      setSuccess("Grounded suggestions are ready for review.");
    } catch (error) {
      setFailure(
        requestErrorMessage(
          error,
          "Change Studio could not generate suggestions.",
        ),
      );
    } finally {
      setBusyKey(undefined);
    }
  }

  async function openExisting(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusyKey("open");
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const next = await getChangeSet(existingId.trim());
      setChangeSet(next);
      setSuccess("Change set loaded.");
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "The change set could not be loaded."),
      );
    } finally {
      setBusyKey(undefined);
    }
  }

  async function updateChangeSet(
    key: string,
    action: (value: ChangeSet) => Promise<ChangeSet>,
    message: string,
  ) {
    if (!changeSet) return;
    setBusyKey(key);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const next = await action(changeSet);
      setChangeSet(next);
      setSuccess(message);
      setEditingId(undefined);
      setDraftText("");
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "The change could not be applied."),
      );
    } finally {
      setBusyKey(undefined);
    }
  }

  function beginEdit(operation: ChangeOperation) {
    setEditingId(operation.id);
    setDraftText(operation.afterText);
  }

  if (busyKey === "initial") {
    return <ChangeStudioLoading />;
  }

  return (
    <main
      className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8"
      id="main-content"
    >
      <div aria-live="polite" className="sr-only">
        {success || failure || ""}
      </div>

      <PageHeader
        description="Compare each proposed resume edit with its original language, requirement, reason, and eligible evidence before you decide."
        eyebrow="Change Studio"
        title="Grounded resume changes"
      />

      <section
        aria-labelledby="open-review-heading"
        className="data-region grid gap-5 p-4 sm:p-5 lg:grid-cols-2"
      >
        <div className="lg:col-span-2">
          <h2
            className="font-semibold text-foreground"
            id="open-review-heading"
          >
            Start or reopen a review
          </h2>
          <p className="mt-1 text-sm leading-6 text-muted">
            Use an ID from a real Job Match analysis or a previously saved
            change set. Meridian does not create placeholder opportunities.
          </p>
        </div>
        <form
          aria-label="Generate suggestions from an analysis"
          className="grid min-w-0 gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end"
          onSubmit={(event) => void generate(event)}
        >
          <div className="space-y-2">
            <FieldLabel htmlFor="analysis-id">Job match analysis ID</FieldLabel>
            <Input
              className="min-w-0"
              id="analysis-id"
              onChange={(event) => setAnalysisId(event.target.value)}
              placeholder="Paste analysis ID"
              required
              value={analysisId}
            />
          </div>
          <Button loading={busyKey === "generate"} type="submit">
            <FileDiff aria-hidden="true" className="size-4" />
            Generate
          </Button>
        </form>
        <form
          aria-label="Open an existing change set"
          className="grid min-w-0 gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end"
          onSubmit={(event) => void openExisting(event)}
        >
          <div className="space-y-2">
            <FieldLabel htmlFor="change-set-id">Saved change set ID</FieldLabel>
            <Input
              className="min-w-0"
              id="change-set-id"
              onChange={(event) => setExistingId(event.target.value)}
              placeholder="Paste change set ID"
              value={existingId}
            />
          </div>
          <Button
            disabled={!existingId.trim()}
            loading={busyKey === "open"}
            type="submit"
            variant="secondary"
          >
            <History aria-hidden="true" className="size-4" />
            Open
          </Button>
        </form>
      </section>

      {failure && (
        <Alert title="Change Studio unavailable" tone="danger">
          {failure}
        </Alert>
      )}
      {success && (
        <Alert title="Ready" tone="success">
          {success}
        </Alert>
      )}

      {!changeSet ? (
        <EmptyState
          description="Open a Job Match analysis to generate grounded suggestions from eligible Career Record evidence."
          title="No change set loaded"
        />
      ) : (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
          <section aria-labelledby="suggestions-heading" className="space-y-4">
            <div className="rounded-lg border border-line bg-surface p-4 shadow-sm">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <h2
                    className="text-lg font-black text-foreground"
                    id="suggestions-heading"
                  >
                    Suggestions
                  </h2>
                  <p className="mt-1 text-sm text-muted">
                    {changeSet.providerName} / {changeSet.providerModel}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    loading={busyKey === "safe"}
                    onClick={() =>
                      void updateChangeSet(
                        "safe",
                        applySafeChanges,
                        "Safe changes applied.",
                      )
                    }
                    variant="secondary"
                  >
                    <ShieldCheck aria-hidden="true" className="size-4" />
                    Approve eligible low-risk
                  </Button>
                  <Button
                    loading={busyKey === "undo"}
                    onClick={() =>
                      void updateChangeSet(
                        "undo",
                        undoChangeSet,
                        "Earlier version restored.",
                      )
                    }
                    variant="ghost"
                  >
                    <Undo2 aria-hidden="true" className="size-4" />
                    Undo
                  </Button>
                  <Button
                    loading={busyKey === "redo"}
                    onClick={() =>
                      void updateChangeSet(
                        "redo",
                        redoChangeSet,
                        "Later version restored.",
                      )
                    }
                    variant="ghost"
                  >
                    <Redo2 aria-hidden="true" className="size-4" />
                    Redo
                  </Button>
                </div>
              </div>
              <p className="mt-3 text-xs leading-5 text-muted">
                {changeSet.scoringDisclaimer}
              </p>
            </div>

            {changeSet.operations.length === 0 ? (
              <EmptyState
                description="No grounded operations were returned for this analysis."
                title="No suggestions"
              />
            ) : (
              <ul className="space-y-4">
                {changeSet.operations.map((operation) => (
                  <li
                    className="rounded-lg border border-line bg-surface p-4 shadow-sm"
                    key={operation.id}
                  >
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div className="space-y-2">
                        <div className="flex flex-wrap gap-2">
                          <Badge tone={statusTone(operation.status)}>
                            {humanize(operation.status)}
                          </Badge>
                          <Badge
                            tone={groundingTone(operation.groundingStatus)}
                          >
                            {humanize(operation.groundingStatus)}
                          </Badge>
                          <Badge tone="neutral">
                            {humanize(operation.risk)} risk
                          </Badge>
                          {operation.locked && (
                            <Badge tone="warning">Locked</Badge>
                          )}
                        </div>
                        <h3 className="text-base font-black text-foreground">
                          {operation.requirementText ??
                            humanize(operation.operationType)}
                        </h3>
                        <p className="max-w-3xl text-sm leading-6 text-muted">
                          {operation.reason}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          disabled={
                            operation.status === "accepted" ||
                            operation.groundingStatus !== "grounded" ||
                            operation.locked
                          }
                          loading={busyKey === `accept-${operation.id}`}
                          onClick={() =>
                            void updateChangeSet(
                              `accept-${operation.id}`,
                              (value) => acceptOperation(value, operation.id),
                              "Suggestion accepted.",
                            )
                          }
                          variant="secondary"
                        >
                          <Check aria-hidden="true" className="size-4" />
                          Accept
                        </Button>
                        <Button
                          disabled={operation.status === "accepted"}
                          loading={busyKey === `reject-${operation.id}`}
                          onClick={() =>
                            void updateChangeSet(
                              `reject-${operation.id}`,
                              (value) => rejectOperation(value, operation.id),
                              "Suggestion rejected.",
                            )
                          }
                          variant="ghost"
                        >
                          <X aria-hidden="true" className="size-4" />
                          Reject
                        </Button>
                        <Button
                          disabled={operation.status === "accepted"}
                          onClick={() => beginEdit(operation)}
                          variant="ghost"
                        >
                          <Pencil aria-hidden="true" className="size-4" />
                          Edit
                        </Button>
                        <Button
                          disabled={
                            operation.locked || operation.status === "accepted"
                          }
                          loading={busyKey === `alt-${operation.id}`}
                          onClick={() =>
                            void updateChangeSet(
                              `alt-${operation.id}`,
                              (value) =>
                                createAlternative(value, operation.id, {
                                  length: "standard",
                                  preserveTerms: [],
                                  tone: "direct",
                                }),
                              "Alternative generated.",
                            )
                          }
                          variant="ghost"
                        >
                          <RotateCcw aria-hidden="true" className="size-4" />
                          Alternative
                        </Button>
                        <Button
                          disabled={operation.status === "accepted"}
                          loading={busyKey === `lock-${operation.id}`}
                          onClick={() =>
                            void updateChangeSet(
                              `lock-${operation.id}`,
                              (value) =>
                                setOperationLocked(
                                  value,
                                  operation.id,
                                  !operation.locked,
                                ),
                              operation.locked
                                ? "Suggestion unlocked."
                                : "Suggestion locked.",
                            )
                          }
                          variant="ghost"
                        >
                          {operation.locked ? (
                            <Unlock aria-hidden="true" className="size-4" />
                          ) : (
                            <Lock aria-hidden="true" className="size-4" />
                          )}
                          {operation.locked ? "Unlock" : "Lock"}
                        </Button>
                      </div>
                    </div>

                    <div className="mt-4 grid gap-3 lg:grid-cols-2">
                      <div className="rounded-lg bg-surface-subtle p-3">
                        <p className="text-xs font-extrabold uppercase text-muted">
                          Before
                        </p>
                        <p className="mt-2 whitespace-pre-wrap text-sm text-muted">
                          {operation.beforeText || "No existing text"}
                        </p>
                      </div>
                      <div className="rounded-lg bg-primary-soft/40 p-3">
                        <p className="text-xs font-extrabold uppercase text-primary">
                          Proposed
                        </p>
                        <p className="mt-2 whitespace-pre-wrap text-sm font-semibold text-foreground">
                          {operation.afterText}
                        </p>
                      </div>
                    </div>

                    {editingId === operation.id && (
                      <form
                        className="mt-4 space-y-3 border-t border-line pt-4"
                        onSubmit={(event) => {
                          event.preventDefault();
                          void updateChangeSet(
                            `edit-${operation.id}`,
                            (value) =>
                              editOperation(value, operation.id, {
                                afterText: draftText,
                              }),
                            "Edited suggestion revalidated.",
                          );
                        }}
                      >
                        <label className="text-sm font-bold text-foreground">
                          Edit suggestion
                          <textarea
                            className="mt-1 min-h-28 w-full resize-y rounded-xl border border-line bg-surface px-3.5 py-3 text-sm text-foreground shadow-sm outline-none focus:border-primary focus:ring-3 focus:ring-primary-soft"
                            maxLength={2000}
                            onChange={(event) =>
                              setDraftText(event.target.value)
                            }
                            required
                            value={draftText}
                          />
                        </label>
                        <div className="flex gap-2">
                          <Button
                            loading={busyKey === `edit-${operation.id}`}
                            type="submit"
                          >
                            <Check aria-hidden="true" className="size-4" />
                            Save edit
                          </Button>
                          <Button
                            onClick={() => setEditingId(undefined)}
                            type="button"
                            variant="ghost"
                          >
                            Cancel
                          </Button>
                        </div>
                      </form>
                    )}

                    <div className="mt-4 border-t border-line pt-4">
                      <h4 className="text-sm font-black text-foreground">
                        Provenance
                      </h4>
                      {operation.claims.length === 0 ? (
                        <Alert
                          className="mt-3"
                          title="No eligible grounding"
                          tone="warning"
                        >
                          This suggestion cannot be accepted until it is
                          grounded.
                        </Alert>
                      ) : (
                        <ul className="mt-3 grid gap-3 md:grid-cols-2">
                          {operation.claims.map((claim) => (
                            <li
                              className="rounded-lg border border-line p-3"
                              key={claim.id}
                            >
                              <div className="flex items-center gap-2">
                                <ShieldCheck
                                  aria-hidden="true"
                                  className="size-4 text-success"
                                />
                                <span className="text-sm font-black text-foreground">
                                  {claim.evidenceTitle}
                                </span>
                              </div>
                              <p className="mt-2 text-sm text-muted">
                                {claim.text}
                              </p>
                              <p className="mt-2 text-xs leading-5 text-muted">
                                {claim.sourceExcerpt}
                              </p>
                              <div className="mt-2 flex flex-wrap gap-2">
                                <Badge tone="neutral">
                                  {humanize(claim.claimKind)}
                                </Badge>
                                <Badge
                                  tone={
                                    claim.validationStatus === "passed"
                                      ? "success"
                                      : "danger"
                                  }
                                >
                                  {humanize(claim.validationStatus)}
                                </Badge>
                              </div>
                            </li>
                          ))}
                        </ul>
                      )}
                      {operation.groundingCodes.some(
                        (code) => code !== "grounded",
                      ) && (
                        <div className="mt-3 flex items-start gap-2 rounded-lg bg-danger-soft p-3 text-sm text-danger-strong">
                          <AlertTriangle
                            aria-hidden="true"
                            className="mt-0.5 size-4"
                          />
                          <span>{operation.groundingCodes.join(", ")}</span>
                        </div>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <aside className="space-y-4">
            <section
              aria-labelledby="current-version-heading"
              className="rounded-lg border border-line bg-surface p-4 shadow-sm"
            >
              <h2
                className="text-lg font-black text-foreground"
                id="current-version-heading"
              >
                Current version
              </h2>
              <p className="mt-1 text-sm text-muted">
                Version {currentVersion?.versionNumber ?? "none"}
              </p>
              <div className="mt-3 min-h-32 whitespace-pre-wrap rounded-lg bg-surface-subtle p-3 text-sm text-foreground">
                {currentVersion?.content || "No accepted changes yet."}
              </div>
            </section>

            <section
              aria-labelledby="questions-heading"
              className="rounded-lg border border-line bg-surface p-4 shadow-sm"
            >
              <div className="flex items-center gap-2">
                <MessageSquare
                  aria-hidden="true"
                  className="size-5 text-primary"
                />
                <h2
                  className="text-lg font-black text-foreground"
                  id="questions-heading"
                >
                  Questions
                </h2>
              </div>
              {changeSet.questions.length === 0 ? (
                <p className="mt-3 text-sm text-muted">
                  No clarifying questions are open.
                </p>
              ) : (
                <ul className="mt-3 space-y-3">
                  {changeSet.questions.map((question) => (
                    <li
                      className="rounded-lg border border-line p-3"
                      key={question.id}
                    >
                      <Badge
                        tone={
                          question.status === "answered" ? "success" : "warning"
                        }
                      >
                        {humanize(question.status)}
                      </Badge>
                      <p className="mt-2 text-sm font-bold text-foreground">
                        {question.question}
                      </p>
                      <p className="mt-1 text-xs leading-5 text-muted">
                        {question.reason}
                      </p>
                      {question.status === "answered" ? (
                        <p className="mt-2 text-sm text-muted">
                          {question.answerText}
                        </p>
                      ) : (
                        <form
                          className="mt-3 space-y-2"
                          onSubmit={(event) => {
                            event.preventDefault();
                            void updateChangeSet(
                              `answer-${question.id}`,
                              (value) =>
                                answerClarification(value, question.id, {
                                  answerText: answers[question.id] ?? "",
                                }),
                              "Answer saved.",
                            );
                          }}
                        >
                          <label className="text-sm font-bold text-foreground">
                            Answer
                            <textarea
                              className="mt-1 min-h-24 w-full resize-y rounded-xl border border-line bg-surface px-3.5 py-3 text-sm text-foreground shadow-sm outline-none focus:border-primary focus:ring-3 focus:ring-primary-soft"
                              maxLength={2000}
                              onChange={(event) =>
                                setAnswers((current) => ({
                                  ...current,
                                  [question.id]: event.target.value,
                                }))
                              }
                              required
                              value={answers[question.id] ?? ""}
                            />
                          </label>
                          <Button
                            loading={busyKey === `answer-${question.id}`}
                            type="submit"
                            variant="secondary"
                          >
                            Save answer
                          </Button>
                        </form>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section
              aria-labelledby="versions-heading"
              className="rounded-lg border border-line bg-surface p-4 shadow-sm"
            >
              <div className="flex items-center gap-2">
                <RotateCcw aria-hidden="true" className="size-5 text-primary" />
                <h2
                  className="text-lg font-black text-foreground"
                  id="versions-heading"
                >
                  Versions
                </h2>
              </div>
              <ul className="mt-3 space-y-2">
                {changeSet.versions.map((version) => (
                  <li
                    className={cn(
                      "flex items-center justify-between gap-3 rounded-lg border p-3",
                      version.id === changeSet.currentVersionId
                        ? "border-primary bg-primary-soft/40"
                        : "border-line",
                    )}
                    key={version.id}
                  >
                    <div>
                      <p className="text-sm font-black text-foreground">
                        {version.title}
                      </p>
                      <p className="text-xs text-muted">
                        Version {version.versionNumber}
                      </p>
                    </div>
                    <Button
                      disabled={version.id === changeSet.currentVersionId}
                      loading={busyKey === `restore-${version.id}`}
                      onClick={() =>
                        void updateChangeSet(
                          `restore-${version.id}`,
                          (value) => restoreVersion(value, version.id),
                          "Version restored.",
                        )
                      }
                      variant="ghost"
                    >
                      Restore
                    </Button>
                  </li>
                ))}
              </ul>
            </section>
          </aside>
        </div>
      )}
    </main>
  );
}

export function ChangeStudioLoading() {
  return (
    <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
      <LoadingSkeleton />
    </main>
  );
}

export function ChangeStudioRouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
      <ErrorState
        description={error.message || "Refresh and try again."}
        onRetry={reset}
        title="Change Studio unavailable"
      />
    </main>
  );
}
