"use client";

import { FileHeart, RefreshCcw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Alert, Button, LoadingSkeleton } from "@careeros/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import { getDocuments } from "../api/resume-health-api";
import type { DocumentSummary } from "../api/types";
import { DocumentList } from "../components/document-list";
import { UploadWorkflow } from "../components/upload-workflow";

export function AccountResumeHealthView() {
  const router = useRouter();
  const [documents, setDocuments] = useState<DocumentSummary[]>();
  const [failure, setFailure] = useState<string>();

  const load = useCallback(async () => {
    try {
      const response = await getDocuments();
      setDocuments(response.data);
      setFailure(undefined);
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "We couldn’t load your private resumes."),
      );
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  return (
    <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
      <header className="mb-6">
        <p className="eyebrow">General document check</p>
        <div className="mt-2 flex items-start gap-3">
          <span className="mt-1 grid size-11 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary">
            <FileHeart aria-hidden="true" className="size-5" />
          </span>
          <div>
            <h1 className="text-2xl font-black tracking-[-0.035em] text-foreground sm:text-3xl">
              Resume Health
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
              Upload a real resume, review uncertain parsing, then calculate an
              explainable internal readiness measurement. No job description is
              required.
            </p>
          </div>
        </div>
      </header>

      <section aria-labelledby="upload-heading">
        <h2 className="mb-3 text-lg font-extrabold" id="upload-heading">
          Upload another resume
        </h2>
        <UploadWorkflow
          access="account"
          onComplete={(result) =>
            router.push(
              `/resume-health/account/processing/${encodeURIComponent(result.job.id)}`,
            )
          }
        />
      </section>

      <section aria-labelledby="documents-heading" className="mt-8">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="text-lg font-extrabold" id="documents-heading">
            Your resumes
          </h2>
          <Button onClick={() => void load()} variant="ghost">
            <RefreshCcw aria-hidden="true" className="size-4" /> Refresh
          </Button>
        </div>
        {failure && (
          <Alert className="mb-4" title="Resumes unavailable" tone="danger">
            {failure}
          </Alert>
        )}
        {!documents && !failure ? (
          <LoadingSkeleton />
        ) : (
          <DocumentList documents={documents ?? []} />
        )}
      </section>
    </main>
  );
}
