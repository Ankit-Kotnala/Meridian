"use client";

import { Clock3 } from "lucide-react";
import { useRouter } from "next/navigation";

import { Alert } from "@rezumi/ui";

import { UploadWorkflow } from "../components/upload-workflow";

export function GuestUploadView() {
  const router = useRouter();
  return (
    <main className="site-container py-8 sm:py-12" id="main-content">
      <header className="mx-auto mb-7 max-w-3xl text-center">
        <p className="eyebrow">Limited guest check</p>
        <h1 className="font-display mt-2 text-3xl font-semibold tracking-[-0.04em] text-foreground sm:text-4xl">
          Check one resume before creating an account
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted sm:text-base">
          Your guest access stays in this browser. The private document and
          report expire automatically unless you explicitly sign in and save
          them to your account.
        </p>
      </header>
      <div className="mx-auto max-w-3xl">
        <Alert className="mb-5" title="Short retention" tone="warning">
          <span className="inline-flex items-start gap-2">
            <Clock3 aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            The exact expiry is shown after upload. You can delete the document
            sooner from the report.
          </span>
        </Alert>
        <UploadWorkflow
          access="guest"
          onComplete={(result) =>
            router.push(
              `/resume-health/guest/processing/${encodeURIComponent(result.job.id)}`,
            )
          }
        />
      </div>
    </main>
  );
}
