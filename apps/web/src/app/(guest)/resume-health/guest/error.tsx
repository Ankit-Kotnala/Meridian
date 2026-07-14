"use client";

import { ErrorState } from "@careeros/ui";

export default function GuestResumeHealthError({
  reset,
}: {
  reset: () => void;
}) {
  return (
    <main className="site-container py-8 sm:py-12" id="main-content">
      <ErrorState
        description="The guest Resume Health workflow could not be loaded. No document state was changed."
        onRetry={reset}
        title="Guest resume check unavailable"
      />
    </main>
  );
}
