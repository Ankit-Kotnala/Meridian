"use client";

import { RefreshCcw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  Alert,
  Button,
  LoadingSkeleton,
  PageHeader,
  SectionHeader,
} from "@careeros/ui";

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
      <PageHeader
        description="Upload a real resume, review uncertain parsing, then calculate an explainable internal readiness measurement. No job description is required."
        eyebrow="General document check"
        title="Resume Health"
      />

      <section aria-labelledby="upload-heading">
        <SectionHeader id="upload-heading" title="Upload another resume" />
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
        <SectionHeader
          actions={
            <Button onClick={() => void load()} variant="ghost">
              <RefreshCcw aria-hidden="true" className="size-4" /> Refresh
            </Button>
          }
          id="documents-heading"
          title="Your resumes"
        />
        {failure && (
          <Alert className="mb-4" title="Resumes unavailable" tone="danger">
            {failure}
          </Alert>
        )}
        {!documents && !failure ? (
          <LoadingSkeleton variant="list" />
        ) : (
          <DocumentList documents={documents ?? []} />
        )}
      </section>
    </main>
  );
}
