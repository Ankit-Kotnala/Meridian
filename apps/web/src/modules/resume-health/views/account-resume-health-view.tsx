"use client";

import {
  BarChart3,
  Download,
  FileSearch,
  Lightbulb,
  RefreshCcw,
  Sparkles,
  Upload,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  Alert,
  Button,
  LoadingSkeleton,
  buttonStyles,
  cn,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import { getDocuments } from "../api/resume-health-api";
import type { DocumentSummary } from "../api/types";
import { DocumentList } from "../components/document-list";
import { UploadWorkflow } from "../components/upload-workflow";

const FEATURES = [
  { icon: BarChart3, label: "Resume Health analysis" },
  { icon: Lightbulb, label: "Smart suggestions" },
  { icon: FileSearch, label: "Keyword matching" },
  { icon: Download, label: "Download report" },
] as const;

const BENEFITS = [
  {
    description: "Structure that parsers can read reliably.",
    icon: FileSearch,
    title: "Readable formatting",
  },
  {
    description: "Prioritized changes you can accept or reject.",
    icon: Lightbulb,
    title: "Tailored suggestions",
  },
  {
    description: "Role language mapped to your reviewed record.",
    icon: Sparkles,
    title: "Keyword alignment",
  },
  {
    description: "Explainable scores with full methodology.",
    icon: BarChart3,
    title: "Instant feedback",
  },
] as const;

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
        requestErrorMessage(error, "We couldn't load your private resumes."),
      );
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  return (
    <main className="workspace-page space-y-5" id="main-content">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-[-0.03em] text-foreground sm:text-3xl">
            Resume Studio
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
            Upload a real resume, review uncertain parsing, then calculate an
            explainable internal readiness measurement. No job description is
            required.
          </p>
        </div>
        <Link
          className={cn(buttonStyles.base, buttonStyles.primary, "shrink-0")}
          href="#upload-zone"
        >
          <Upload aria-hidden="true" className="size-4" />
          Upload Resume
        </Link>
      </header>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(16rem,0.85fr)]">
        <div className="space-y-5">
          <section aria-labelledby="upload-heading" className="workspace-panel">
            <div className="border-b border-line px-4 py-3.5 sm:px-5">
              <h2 className="text-sm font-bold text-foreground" id="upload-heading">
                Upload a resume
              </h2>
            </div>
            <div className="p-4 sm:p-5" id="upload-zone">
              <UploadWorkflow
                access="account"
                onComplete={(result) =>
                  router.push(
                    `/resume-health/account/processing/${encodeURIComponent(result.job.id)}`,
                  )
                }
              />
            </div>
            <ul className="grid grid-cols-2 divide-x divide-line border-t border-line sm:grid-cols-4">
              {FEATURES.map(({ icon: Icon, label }) => (
                <li
                  className="flex flex-col items-center gap-2 px-3 py-4 text-center"
                  key={label}
                >
                  <Icon
                    aria-hidden="true"
                    className="size-5 text-primary"
                    strokeWidth={1.75}
                  />
                  <span className="text-xs font-semibold text-muted-strong">
                    {label}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </div>

        <section
          aria-labelledby="documents-heading"
          className="workspace-panel min-w-0"
        >
          <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3.5 sm:px-5">
            <h2 className="text-sm font-bold text-foreground" id="documents-heading">
              Recent resumes
            </h2>
            <Button onClick={() => void load()} variant="ghost">
              <RefreshCcw aria-hidden="true" className="size-4" />
              Refresh
            </Button>
          </div>
          {failure && (
            <Alert className="m-4" title="Resumes unavailable" tone="danger">
              {failure}
            </Alert>
          )}
          {!documents && !failure ? (
            <LoadingSkeleton className="p-4" variant="list" />
          ) : (
            <DocumentList documents={documents ?? []} variant="sidebar" />
          )}
        </section>
      </div>

      <section
        aria-labelledby="benefits-heading"
        className="workspace-feature-grid rounded-[var(--radius-card)] border border-line px-4 py-6 sm:px-6"
      >
        <h2
          className="text-base font-bold text-foreground"
          id="benefits-heading"
        >
          Why use Rezumi Resume Studio?
        </h2>
        <ul className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {BENEFITS.map(({ description, icon: Icon, title }) => (
            <li className="min-w-0" key={title}>
              <Icon
                aria-hidden="true"
                className="size-5 text-primary"
                strokeWidth={1.75}
              />
              <h3 className="mt-2 text-sm font-bold text-foreground">{title}</h3>
              <p className="mt-1 text-xs leading-5 text-muted">{description}</p>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
