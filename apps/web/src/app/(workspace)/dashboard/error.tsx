"use client";

import { ErrorState } from "@careeros/ui";

export default function DashboardError({ reset }: { reset: () => void }) {
  return (
    <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
      <ErrorState
        description="Your protected workspace could not be loaded. No account data was changed."
        onRetry={reset}
        title="Workspace unavailable"
      />
    </main>
  );
}
