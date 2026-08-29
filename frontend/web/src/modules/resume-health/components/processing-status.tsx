"use client";

import { Ban, FileSearch, RefreshCcw, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import {
  Alert,
  Button,
  Card,
  ErrorState,
  Progress,
  buttonStyles,
  cn,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  cancelProcessingJob,
  newIdempotencyKey,
} from "../api/resume-health-api";
import type { ResumeHealthAccess } from "../api/types";
import { useProcessingJob } from "../hooks/use-processing-job";

const stageLabels = {
  queued: "Waiting for a protected worker",
  admission: "Verifying document limits",
  malwareScan: "Scanning the quarantined file",
  extraction: "Extracting text and layout",
  canonicalization: "Structuring fields for your review",
  analysis: "Calculating the internal Resume Health measure",
  complete: "Processing complete",
  cleanup: "Cleaning the isolated workspace",
} as const;

export function ProcessingStatus({
  access,
  jobId,
  onSucceeded,
}: {
  access: ResumeHealthAccess;
  jobId: string;
  onSucceeded: (result: { id: string; type: "analysis" | "document" }) => void;
}) {
  const { failure, job, retry } = useProcessingJob(access, jobId);
  const [cancelling, setCancelling] = useState(false);
  const [cancelFailure, setCancelFailure] = useState<string>();
  const completed = useRef(false);
  const retryScheduled =
    job?.status === "failed" && job.error?.retryable === true;
  const terminalFailure =
    job?.status === "deadLettered" ||
    (job?.status === "failed" && !retryScheduled);

  useEffect(() => {
    completed.current = false;
  }, [jobId]);

  useEffect(() => {
    if (
      job?.status === "succeeded" &&
      job.resultId &&
      job.resultType &&
      !completed.current
    ) {
      completed.current = true;
      onSucceeded({ id: job.resultId, type: job.resultType });
    }
  }, [job, onSucceeded]);

  async function cancel() {
    setCancelling(true);
    setCancelFailure(undefined);
    try {
      await cancelProcessingJob(access, jobId, newIdempotencyKey());
      retry();
    } catch (error) {
      setCancelFailure(
        requestErrorMessage(error, "We couldn’t cancel this processing job."),
      );
    } finally {
      setCancelling(false);
    }
  }

  if (!job && failure) {
    return (
      <ErrorState
        description={failure}
        onRetry={retry}
        title="Processing status unavailable"
      />
    );
  }

  const returnPath =
    access === "account" ? "/resume-health/account" : "/resume-health/guest";

  return (
    <Card className="p-5 sm:p-7">
      <div className="mx-auto max-w-2xl text-center">
        <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-primary-soft text-primary">
          {job?.stage === "malwareScan" ? (
            <ShieldCheck aria-hidden="true" className="size-6" />
          ) : (
            <FileSearch aria-hidden="true" className="size-6" />
          )}
        </span>
        <p className="eyebrow mt-5">Secure document processing</p>
        <h1 className="mt-2 text-2xl font-black tracking-[-0.035em] text-foreground sm:text-3xl">
          {retryScheduled
            ? "Secure processing will retry"
            : terminalFailure
              ? job?.jobType === "delete"
                ? "This resume could not be deleted"
                : "This resume could not be processed"
              : job?.status === "cancelled"
                ? "Processing was cancelled"
                : job?.jobType === "delete" && job.status === "succeeded"
                  ? "Resume deletion complete"
                  : job?.jobType === "delete"
                    ? "Deleting your resume"
                    : job?.jobType === "analyze"
                      ? "Calculating Resume Health"
                      : "Preparing your resume for review"}
        </h1>
        <p aria-live="polite" className="mt-3 text-sm leading-6 text-muted">
          {retryScheduled
            ? "A temporary dependency is unavailable. The protected worker will retry automatically."
            : job
              ? stageLabels[job.stage]
              : "Loading the durable processing status…"}
        </p>

        {job && !terminalFailure && job.status !== "cancelled" && (
          <Progress
            className="mt-7 text-left"
            label={retryScheduled ? "Waiting to retry" : stageLabels[job.stage]}
            value={job.progress ?? null}
          />
        )}

        {(failure || cancelFailure) && (
          <Alert
            className="mt-6 text-left"
            title="Status needs attention"
            tone="warning"
          >
            {cancelFailure ?? failure}
            <Button className="mt-3" onClick={retry} variant="secondary">
              <RefreshCcw aria-hidden="true" className="size-4" /> Refresh
              status
            </Button>
          </Alert>
        )}

        {retryScheduled && (
          <Alert
            className="mt-6 text-left"
            title="Retry scheduled"
            tone="warning"
          >
            No unsafe output was released. Keep this page open while the durable
            job retries, or cancel processing below.
          </Alert>
        )}

        {terminalFailure && (
          <Alert
            className="mt-6 text-left"
            title="Safe processing failure"
            tone="danger"
          >
            {job?.error?.message ??
              "The file remains unavailable for use. Try a clean supported document."}
          </Alert>
        )}

        {job?.jobType === "delete" && job.status === "succeeded" && (
          <Alert
            className="mt-6 text-left"
            title="Private document removed"
            tone="success"
          >
            The source file, parsed derivatives, and reports completed the
            durable deletion workflow.
          </Alert>
        )}

        <div className="mt-7 flex flex-col-reverse gap-3 sm:flex-row sm:justify-center">
          <Link
            className={cn(buttonStyles.base, buttonStyles.secondary)}
            href={returnPath}
          >
            Return to Resume Health
          </Link>
          {job &&
            job.jobType !== "delete" &&
            (new Set(["queued", "running"]).has(job.status) ||
              retryScheduled) && (
              <Button
                loading={cancelling}
                loadingLabel="Cancelling…"
                onClick={() => void cancel()}
                variant="ghost"
              >
                <Ban aria-hidden="true" className="size-4" /> Cancel processing
              </Button>
            )}
        </div>
      </div>
    </Card>
  );
}
