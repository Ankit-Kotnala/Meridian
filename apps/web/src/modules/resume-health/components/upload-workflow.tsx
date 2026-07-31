"use client";

import { ShieldCheck, XCircle } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";

import {
  Alert,
  Button,
  Card,
  ErrorState,
  FileUploadField,
  formatBytes,
  LoadingSkeleton,
  Progress,
} from "@careeros/ui";

import {
  ApiRequestError,
  requestErrorMessage,
} from "@/shared/api/browser-request";

import {
  createUploadIntent,
  finalizeUpload,
  getUploadPolicy,
  newIdempotencyKey,
  uploadFile,
} from "../api/resume-health-api";
import type {
  FinalizeUpload,
  ResumeHealthAccess,
  UploadIntent,
  UploadPolicy,
} from "../api/types";
import { validateUpload } from "../validation/upload-validation";

type UploadStage = "idle" | "creatingIntent" | "uploading" | "finalizing";

type PendingUploadAttempt = {
  file: File;
  intent: UploadIntent;
  finalizeKey: string;
  transferred: boolean;
};

export function UploadWorkflow({
  access,
  onComplete,
}: {
  access: ResumeHealthAccess;
  onComplete: (result: FinalizeUpload) => void;
}) {
  const [policy, setPolicy] = useState<UploadPolicy>();
  const [policyFailure, setPolicyFailure] = useState<string>();
  const [policyRevision, setPolicyRevision] = useState(0);
  const [file, setFile] = useState<File>();
  const [fileError, setFileError] = useState<string>();
  const [failure, setFailure] = useState<string>();
  const [hasPendingAttempt, setHasPendingAttempt] = useState(false);
  const [stage, setStage] = useState<UploadStage>("idle");
  const [progress, setProgress] = useState<number | null>(null);
  const transfer = useRef<AbortController | undefined>(undefined);
  const pendingAttempt = useRef<PendingUploadAttempt | undefined>(undefined);

  useEffect(() => {
    let active = true;
    void getUploadPolicy(access)
      .then((value) => {
        if (!active) return;
        setPolicy(value);
        setPolicyFailure(undefined);
      })
      .catch((error) => {
        if (!active) return;
        setPolicyFailure(
          requestErrorMessage(error, "We couldn’t load the upload policy."),
        );
      });
    return () => {
      active = false;
      transfer.current?.abort();
    };
  }, [access, policyRevision]);

  function selectFile(next: File | undefined) {
    pendingAttempt.current = undefined;
    setHasPendingAttempt(false);
    setFile(next);
    setFileError(undefined);
    setFailure(undefined);
    if (next && policy) {
      const result = validateUpload(next, policy);
      if ("error" in result) setFileError(result.error);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file || !policy) {
      setFileError("Choose a PDF or DOCX file.");
      return;
    }
    const validation = validateUpload(file, policy);
    if ("error" in validation) {
      setFileError(validation.error);
      return;
    }
    setFailure(undefined);
    setFileError(undefined);
    const controller = new AbortController();
    transfer.current = controller;
    try {
      let attempt = pendingAttempt.current;
      const expiredBeforeTransfer =
        attempt &&
        !attempt.transferred &&
        new Date(attempt.intent.expiresAt).getTime() <= Date.now();
      if (!attempt || attempt.file !== file || expiredBeforeTransfer) {
        setStage("creatingIntent");
        attempt = {
          file,
          intent: await createUploadIntent(access, validation.input),
          finalizeKey: newIdempotencyKey(),
          transferred: false,
        };
        pendingAttempt.current = attempt;
        setHasPendingAttempt(true);
      }
      if (!attempt.transferred) {
        setStage("uploading");
        setProgress(0);
        await uploadFile(attempt.intent, file, setProgress, controller.signal);
        attempt.transferred = true;
      }
      setStage("finalizing");
      setProgress(100);
      const result = await finalizeUpload(
        access,
        attempt.intent.uploadId,
        attempt.finalizeKey,
      );
      pendingAttempt.current = undefined;
      setHasPendingAttempt(false);
      onComplete(result);
    } catch (error) {
      if (
        error instanceof ApiRequestError &&
        new Set([404, 409, 410, 413, 415, 422]).has(error.failure.status)
      ) {
        pendingAttempt.current = undefined;
        setHasPendingAttempt(false);
      }
      if (controller.signal.aborted) {
        setFailure(
          "The transfer was cancelled. Retry to continue the same private upload.",
        );
      } else {
        setFailure(
          requestErrorMessage(
            error,
            error instanceof Error
              ? error.message
              : "We couldn’t upload this resume.",
          ),
        );
      }
      setStage("idle");
      setProgress(null);
    } finally {
      if (transfer.current === controller) transfer.current = undefined;
    }
  }

  if (!policy && !policyFailure) return <LoadingSkeleton />;
  if (!policy) {
    return (
      <ErrorState
        description={policyFailure ?? "The upload policy is unavailable."}
        onRetry={() => {
          setPolicyFailure(undefined);
          setPolicyRevision((value) => value + 1);
        }}
        title="Secure upload unavailable"
      />
    );
  }

  const working = stage !== "idle";
  const label =
    stage === "creatingIntent"
      ? "Preparing private upload"
      : stage === "uploading"
        ? "Uploading resume"
        : stage === "finalizing"
          ? "Securing upload"
          : "Upload resume";
  const formatLimits = [
    `Maximum ${formatBytes(policy.maxBytes)}.`,
    policy.acceptedMediaTypes.includes("application/pdf")
      ? `PDFs are limited to ${policy.maxPages} pages.`
      : undefined,
    policy.acceptedMediaTypes.includes(
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
      ? "DOCX files are bounded by archive and extracted-content safety limits."
      : undefined,
    "Actual bytes, type, format-specific safety limits, and malware status are checked after upload.",
  ]
    .filter((part): part is string => part !== undefined)
    .join(" ");

  return (
    <Card className="p-5 sm:p-6">
      <form className="space-y-5" onSubmit={submit}>
        <FileUploadField
          accept={policy.acceptedMediaTypes.join(",")}
          disabled={working}
          error={fileError}
          hint={formatLimits}
          id={`resume-file-${access}`}
          label="Resume file"
          onFileChange={selectFile}
          selectedFile={file}
        />
        {failure && (
          <Alert title="Upload not completed" tone="danger">
            <span>{failure}</span>
            {hasPendingAttempt && (
              <span className="mt-1 block">
                Retry safely reuses this upload and its completion key; it does
                not reserve another document slot.
              </span>
            )}
          </Alert>
        )}
        {working && (
          <div aria-live="polite" className="rounded-xl bg-surface-subtle p-4">
            <Progress
              label={label}
              value={stage === "uploading" ? progress : null}
            />
            <p className="mt-3 text-xs leading-5 text-muted">
              Keep this page open until CareerOS confirms the private upload.
            </p>
          </div>
        )}
        <Alert title="Private admission pipeline" tone="info">
          <span className="inline-flex items-start gap-2">
            <ShieldCheck
              aria-hidden="true"
              className="mt-0.5 size-4 shrink-0"
            />
            New files stay quarantined while CareerOS verifies their signature,
            limits, and malware status. Uploaded content is never executed.
          </span>
        </Alert>
        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          {stage === "uploading" && (
            <Button
              onClick={() => transfer.current?.abort()}
              type="button"
              variant="secondary"
            >
              <XCircle aria-hidden="true" className="size-4" /> Cancel upload
            </Button>
          )}
          <Button
            disabled={!file || Boolean(fileError)}
            loading={working}
            loadingLabel={`${label}…`}
            type="submit"
          >
            {hasPendingAttempt
              ? "Retry upload and review"
              : "Upload and review"}
          </Button>
        </div>
      </form>
    </Card>
  );
}
