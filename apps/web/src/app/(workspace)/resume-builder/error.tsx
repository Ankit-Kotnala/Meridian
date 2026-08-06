"use client";

import { ErrorState } from "@rezumi/ui";

export default function ResumeBuilderError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
      <ErrorState
        description="Refresh the workspace and try again."
        onRetry={reset}
        title="Resume Builder could not load"
      />
    </main>
  );
}
