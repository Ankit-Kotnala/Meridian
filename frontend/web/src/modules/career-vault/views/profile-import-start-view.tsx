"use client";

import { FileDiff, RefreshCcw } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  buttonStyles,
  cn,
} from "@rezumi/ui";

import {
  ApiRequestError,
  requestErrorMessage,
} from "@/shared/api/browser-request";

import {
  createProfileImportProposals,
  listProfileImportProposals,
} from "../api/career-vault-api";
import type { ProfileImportBatch } from "../api/types";

/**
 * Shows the proposals derived from a reviewed resume snapshot, or, when no
 * snapshot is named, the proposals the account already has awaiting a decision.
 */
export function ProfileImportStartView({
  documentId,
  snapshotId,
}: {
  documentId?: string;
  snapshotId?: string;
} = {}) {
  const [batch, setBatch] = useState<ProfileImportBatch>();
  const [failure, setFailure] = useState<string>();

  const load = useCallback(async () => {
    setFailure(undefined);
    try {
      setBatch(
        documentId !== undefined && snapshotId !== undefined
          ? await createProfileImportProposals(documentId, snapshotId)
          : {
              appliedCount: 0,
              proposals: (await listProfileImportProposals()).filter(
                (proposal) => proposal.status === "pending",
              ),
              questions: [],
            },
      );
    } catch (error) {
      if (error instanceof ApiRequestError) {
        if (error.failure.code === "career_record_source_unavailable") {
          setFailure(
            "Parsed field review is not complete, or the reviewed snapshot no longer matches this resume. Open Resume Health, finish reviewing the extracted fields, then try again.",
          );
          return;
        }
        if (error.failure.code === "career_record_conflict") {
          setFailure(
            "Import is already running or was just created. Refresh this page in a moment.",
          );
          return;
        }
      }
      setFailure(
        requestErrorMessage(
          error,
          "We couldn’t load proposals from your reviewed resume.",
        ),
      );
    }
  }, [documentId, snapshotId]);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  if (!batch && !failure) {
    return (
      <main className="mx-auto max-w-5xl p-4 sm:p-6 lg:p-8" id="main-content">
        <LoadingSkeleton />
      </main>
    );
  }
  if (!batch) {
    return (
      <main className="mx-auto max-w-5xl p-4 sm:p-6 lg:p-8" id="main-content">
        <ErrorState
          description={
            failure ?? "The reviewed resume snapshot is unavailable."
          }
          onRetry={load}
          title="Career Record import unavailable"
        />
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-5xl p-4 sm:p-6 lg:p-8" id="main-content">
      <header className="mb-6">
        <p className="eyebrow">Typed resume import</p>
        <h1 className="mt-2 text-2xl font-black tracking-[-0.035em] sm:text-3xl">
          Review before adding facts
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
          These proposals come only from fields you reviewed in Resume Health.
          Nothing has been added to your Career Record yet.
        </p>
      </header>

      {failure && (
        <Alert className="mb-5" title="Proposal refresh failed" tone="warning">
          {failure}
          <Button
            className="mt-3"
            onClick={() => void load()}
            variant="secondary"
          >
            <RefreshCcw aria-hidden="true" className="size-4" /> Try again
          </Button>
        </Alert>
      )}

      {batch.questions.length > 0 && (
        <Alert
          className="mb-5"
          title="Some records need more information"
          tone="info"
        >
          <ul className="mt-2 space-y-2">
            {batch.questions.map((question) => (
              <li key={question.semanticEntityId}>
                Missing reviewed fields:{" "}
                {question.missingFields
                  .map((field) => field.replaceAll("_", " "))
                  .join(", ")}
                . No Career Record fact was proposed for this item.
              </li>
            ))}
          </ul>
        </Alert>
      )}

      {batch.proposals.length === 0 ? (
        <EmptyState
          action={
            <Link
              className={cn(buttonStyles.base, buttonStyles.secondary)}
              href="/career-profile"
            >
              Return to Career Profile
            </Link>
          }
          description={
            documentId === undefined
              ? "Every proposal from your reviewed resume has already been accepted or rejected. Nothing is waiting for a decision."
              : "The snapshot had no complete reviewed fields eligible for a proposal. Missing values remain questions rather than inferred facts."
          }
          title={
            documentId === undefined
              ? "Nothing waiting for review"
              : "No import proposals"
          }
        />
      ) : (
        <div className="space-y-4">
          {batch.proposals.map((proposal) => (
            <Card
              className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between"
              key={proposal.id}
            >
              <div className="flex items-start gap-3">
                <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary">
                  <FileDiff aria-hidden="true" className="size-5" />
                </span>
                <div>
                  <h2 className="font-extrabold">
                    {proposal.changes
                      .map((change) => change.label)
                      .slice(0, 3)
                      .join(", ")}
                  </h2>
                  <p className="mt-1 text-sm text-muted">
                    {proposal.changes.length} reviewed{" "}
                    {proposal.changes.length === 1 ? "field" : "fields"} ·{" "}
                    {proposal.status}
                  </p>
                </div>
              </div>
              <Link
                className={cn(buttonStyles.base, buttonStyles.primary)}
                href={`/career-profile/imports/${encodeURIComponent(proposal.id)}`}
              >
                Review proposal
              </Link>
            </Card>
          ))}
        </div>
      )}
    </main>
  );
}
