"use client";

import { ErrorState } from "@rezumi/ui";

export default function AccountResumeHealthError({
  reset,
}: {
  reset: () => void;
}) {
  return (
    <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
      <ErrorState
        description="Your private Resume Health workspace could not be loaded. No document state was changed."
        onRetry={reset}
        title="Resume Health unavailable"
      />
    </main>
  );
}
