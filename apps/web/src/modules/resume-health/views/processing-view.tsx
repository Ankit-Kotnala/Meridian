"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";

import type { ResumeHealthAccess } from "../api/types";
import { ProcessingStatus } from "../components/processing-status";

export function ProcessingView({
  access,
  jobId,
}: {
  access: ResumeHealthAccess;
  jobId: string;
}) {
  const router = useRouter();
  const prefix =
    access === "account" ? "/resume-health/account" : "/resume-health/guest";
  const onSucceeded = useCallback(
    ({ id, type }: { id: string; type: "analysis" | "document" }) => {
      router.replace(
        `${prefix}/${type === "analysis" ? "report" : "review"}/${encodeURIComponent(id)}`,
      );
    },
    [prefix, router],
  );
  return (
    <main
      className={
        access === "account"
          ? "mx-auto max-w-5xl p-4 sm:p-6 lg:p-8"
          : "site-container py-8 sm:py-12"
      }
      id="main-content"
    >
      <ProcessingStatus
        access={access}
        jobId={jobId}
        onSucceeded={onSucceeded}
      />
    </main>
  );
}
