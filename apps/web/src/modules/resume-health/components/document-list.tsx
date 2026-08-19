"use client";

import { Clock3, FileCheck2, FileWarning, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";

import {
  Alert,
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  buttonStyles,
  cn,
  formatBytes,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import { deleteDocument } from "../api/resume-health-api";
import type { DocumentSummary } from "../api/types";

const statusPresentation = {
  quarantined: { label: "Quarantined", tone: "warning" as const },
  processing: { label: "Processing", tone: "warning" as const },
  reviewReady: { label: "Ready to review", tone: "success" as const },
  failed: { label: "Processing failed", tone: "danger" as const },
  cancelled: { label: "Cancelled", tone: "neutral" as const },
  deleting: { label: "Deletion scheduled", tone: "neutral" as const },
};

function date(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function DocumentList({ documents }: { documents: DocumentSummary[] }) {
  const router = useRouter();
  const [pending, setPending] = useState<DocumentSummary>();
  const [deleting, setDeleting] = useState(false);
  const [failure, setFailure] = useState<string>();

  async function remove() {
    if (!pending) return;
    setDeleting(true);
    setFailure(undefined);
    try {
      const accepted = await deleteDocument(
        "account",
        pending.id,
        pending.version,
      );
      setPending(undefined);
      router.push(
        `/resume-health/account/processing/${encodeURIComponent(accepted.job.id)}`,
      );
    } catch (error) {
      setFailure(
        requestErrorMessage(
          error,
          "We couldn’t delete this resume. Refetch the latest version and try again.",
        ),
      );
    } finally {
      setDeleting(false);
    }
  }

  if (documents.length === 0) {
    return (
      <EmptyState
        description="Upload a real PDF or DOCX to create your first private parse and Resume Health report."
        title="No resumes uploaded"
      />
    );
  }

  return (
    <>
      {failure && (
        <Alert className="mb-4" title="Resume not deleted" tone="danger">
          {failure}
        </Alert>
      )}
      <ul
        aria-label="Your uploaded resumes"
        className="grid gap-4 lg:grid-cols-2"
      >
        {documents.map((document) => {
          const status = document.latestAnalysisId
            ? { label: "Report ready", tone: "success" as const }
            : statusPresentation[document.status];
          const nextHref = document.latestAnalysisId
            ? `/resume-health/account/report/${encodeURIComponent(document.latestAnalysisId)}`
            : document.status === "reviewReady"
              ? `/resume-health/account/review/${encodeURIComponent(document.id)}`
              : undefined;
          return (
            <li key={document.id}>
              <Card className="h-full p-5">
                <div className="flex items-start gap-3">
                  <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary">
                    {document.status === "failed" ? (
                      <FileWarning aria-hidden="true" className="size-5" />
                    ) : (
                      <FileCheck2 aria-hidden="true" className="size-5" />
                    )}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-extrabold text-foreground">
                      {document.displayFilename}
                    </p>
                    <p className="mt-1 text-xs text-muted">
                      {formatBytes(document.sizeBytes)} · uploaded{" "}
                      {date(document.createdAt)}
                    </p>
                    <Badge className="mt-3" tone={status.tone}>
                      {status.label}
                    </Badge>
                  </div>
                </div>
                {document.expiresAt && (
                  <p className="mt-4 flex items-start gap-2 text-xs leading-5 text-muted">
                    <Clock3
                      aria-hidden="true"
                      className="mt-0.5 size-3.5 shrink-0"
                    />
                    Scheduled to expire {date(document.expiresAt)}
                  </p>
                )}
                <div className="mt-5 flex flex-wrap gap-2 border-t border-line pt-4">
                  {nextHref && (
                    <Link
                      className={cn(buttonStyles.base, buttonStyles.secondary)}
                      href={nextHref}
                    >
                      {document.latestAnalysisId
                        ? "Open report"
                        : "Review parse"}
                    </Link>
                  )}
                  {document.status !== "deleting" && (
                    <Button
                      aria-label={`Delete ${document.displayFilename}`}
                      onClick={() => setPending(document)}
                      variant="ghost"
                    >
                      <Trash2 aria-hidden="true" className="size-4" /> Delete
                    </Button>
                  )}
                </div>
              </Card>
            </li>
          );
        })}
      </ul>
      <ConfirmDialog
        confirmLabel="Delete resume"
        description="This removes the private source document, parsed derivatives, active processing, and reports according to the documented deletion policy. This cannot be undone."
        loading={deleting}
        onConfirm={() => void remove()}
        onOpenChange={(open) => {
          if (!open && !deleting) setPending(undefined);
        }}
        open={Boolean(pending)}
        title="Delete this resume?"
      />
    </>
  );
}
