"use client";

import { Check, FileDiff, RefreshCcw, ShieldAlert, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  Alert,
  ApprovalPanel,
  Badge,
  Button,
  Card,
  ConfirmDialog,
  ErrorState,
  LoadingSkeleton,
  buttonStyles,
  cn,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  ApiRequestError,
  acceptProfileImportProposal,
  getProfileImportProposal,
  rejectProfileImportProposal,
} from "../api/career-vault-api";
import type { ProfileImportProposal } from "../api/types";
import { ProvenanceList } from "../components/evidence-semantics";
import { TextareaField } from "../components/form-controls";

export function ProfileImportReviewView({
  proposalId,
}: {
  proposalId: string;
}) {
  const [proposal, setProposal] = useState<ProfileImportProposal>();
  const [values, setValues] = useState<Record<string, string>>({});
  const [failure, setFailure] = useState<string>();
  const [loading, setLoading] = useState(false);
  const [pendingAction, setPendingAction] = useState<"accept" | "reject">();
  const acceptIdempotencyKey = useRef(crypto.randomUUID());
  const rejectIdempotencyKey = useRef(crypto.randomUUID());

  const load = useCallback(async () => {
    setFailure(undefined);
    try {
      const next = await getProfileImportProposal(proposalId);
      setProposal(next);
      setValues(
        Object.fromEntries(
          next.changes.map((change) => [change.id, change.proposedValue]),
        ),
      );
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "We couldn’t load this profile proposal."),
      );
    }
  }, [proposalId]);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  async function resolve() {
    if (!proposal || !pendingAction) return;
    setLoading(true);
    setFailure(undefined);
    try {
      const next =
        pendingAction === "accept"
          ? await acceptProfileImportProposal(
              proposal,
              values,
              acceptIdempotencyKey.current,
            )
          : await rejectProfileImportProposal(
              proposal,
              rejectIdempotencyKey.current,
            );
      setProposal(next);
      setPendingAction(undefined);
    } catch (error) {
      setPendingAction(undefined);
      setFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This proposal or profile changed in another tab. Reload before deciding."
          : requestErrorMessage(error, "We couldn’t save your decision."),
      );
    } finally {
      setLoading(false);
    }
  }

  if (!proposal && !failure) {
    return (
      <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
        <LoadingSkeleton />
      </main>
    );
  }
  if (!proposal) {
    return (
      <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
        <ErrorState
          description={failure ?? "This profile proposal is unavailable."}
          onRetry={load}
          title="Profile proposal unavailable"
        />
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
      <header className="mb-6">
        <p className="eyebrow">Resume import proposal</p>
        <div className="mt-2 flex items-start gap-3">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary">
            <FileDiff aria-hidden="true" className="size-5" />
          </span>
          <div>
            <h1 className="text-2xl font-black tracking-[-0.035em] sm:text-3xl">
              Review proposed Career Record facts
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
              Meridian extracted these suggestions from{" "}
              {proposal.sourceDocumentName}. Nothing is applied until you
              explicitly accept this review.
            </p>
          </div>
        </div>
      </header>

      {failure && (
        <Alert className="mb-5" title="Decision not saved" tone="danger">
          {failure}
          <Button
            className="mt-3"
            onClick={() => void load()}
            variant="secondary"
          >
            <RefreshCcw aria-hidden="true" className="size-4" /> Reload latest
          </Button>
        </Alert>
      )}
      {proposal.status !== "pending" && (
        <Alert
          className="mb-5"
          title={
            proposal.status === "accepted"
              ? "Proposal accepted"
              : "Proposal rejected"
          }
          tone={proposal.status === "accepted" ? "success" : "info"}
        >
          This decision is recorded. The original imported source and proposal
          remain available for audit.
        </Alert>
      )}
      {!proposal.sourceAvailable && proposal.status === "pending" && (
        <Alert
          className="mb-5"
          title="Reviewed source is no longer available"
          tone="warning"
        >
          This proposal remains in the audit history, but it cannot be accepted
          because the reviewed resume snapshot is unavailable.
        </Alert>
      )}

      <div className="space-y-5">
        {proposal.changes.map((change) => (
          <Card className="overflow-hidden" key={change.id}>
            <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line bg-surface-subtle px-5 py-4">
              <div>
                <h2 className="font-extrabold">{change.label}</h2>
                <p className="mt-1 text-xs text-muted">
                  Typed field: {change.field}
                </p>
              </div>
              {change.conflict && (
                <Badge tone="warning">Conflict review required</Badge>
              )}
            </header>
            <div className="grid gap-5 p-5 lg:grid-cols-2">
              <div>
                <p className="text-sm font-extrabold">Current record value</p>
                <blockquote className="mt-3 min-h-28 whitespace-pre-wrap rounded-xl border border-line bg-surface p-4 text-sm leading-6 text-muted">
                  {change.currentValue || "No current value"}
                </blockquote>
              </div>
              <TextareaField
                disabled={proposal.status !== "pending"}
                id={`proposal-${change.id}`}
                label="Proposed value (editable before acceptance)"
                maxLength={8_000}
                onChange={(event) =>
                  setValues((current) => ({
                    ...current,
                    [change.id]: event.target.value,
                  }))
                }
                value={values[change.id] ?? ""}
              />
            </div>
            {change.conflict && (
              <div className="mx-5 mb-5 flex items-start gap-2 rounded-xl border border-amber-200 bg-warning-soft p-3 text-sm text-warning-strong">
                <ShieldAlert
                  aria-hidden="true"
                  className="mt-0.5 size-4 shrink-0"
                />
                <span>
                  <strong>Conflict:</strong> {change.conflict}. Meridian will not
                  resolve this silently.
                </span>
              </div>
            )}
            <details className="mx-5 mb-5 rounded-xl border border-line p-3">
              <summary className="min-h-10 cursor-pointer py-2 text-sm font-bold text-primary">
                View supporting source
              </summary>
              <div className="mt-3">
                <ProvenanceList values={[change.source]} />
              </div>
            </details>
          </Card>
        ))}
      </div>

      {proposal.status === "pending" && (
        <ApprovalPanel
          actions={
            <>
              <Button
                onClick={() => setPendingAction("reject")}
                variant="secondary"
              >
                <X aria-hidden="true" className="size-4" /> Reject proposal
              </Button>
              <Button
                disabled={!proposal.sourceAvailable}
                onClick={() => setPendingAction("accept")}
              >
                <Check aria-hidden="true" className="size-4" /> Accept reviewed
                changes
              </Button>
            </>
          }
          className="sticky bottom-3 z-20 mt-5 shadow-[var(--shadow-md)]"
          evidence={`Source: ${proposal.sourceDocumentName}. The original proposal remains available for audit.`}
          title="Decide what enters your career record"
        >
          Accepting creates or updates only the reviewed values shown above.
          Rejecting leaves the current Career Record unchanged.
        </ApprovalPanel>
      )}

      <Link
        className={cn(buttonStyles.base, buttonStyles.secondary, "mt-5")}
        href="/career-profile"
      >
        Return to Career Profile
      </Link>

      <ConfirmDialog
        confirmLabel={
          pendingAction === "reject" ? "Reject proposal" : "Accept changes"
        }
        description={
          pendingAction === "reject"
            ? "The current Career Profile remains unchanged. The proposal and source are retained for audit."
            : "Only the reviewed values shown on this page will update the confirmed Career Record."
        }
        loading={loading}
        onConfirm={() => void resolve()}
        onOpenChange={(open) => {
          if (!open && !loading) setPendingAction(undefined);
        }}
        open={Boolean(pendingAction)}
        title={
          pendingAction === "reject"
            ? "Reject this proposal?"
            : "Apply these reviewed changes?"
        }
      />
    </main>
  );
}
