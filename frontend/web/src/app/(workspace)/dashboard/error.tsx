"use client";

import { ErrorState } from "@rezumi/ui";

export default function DashboardError({ reset }: { reset: () => void }) {
  return (
    <main className="workspace-page" id="main-content">
      <ErrorState
        description="Your protected workspace could not be loaded. No account data was changed."
        onRetry={reset}
        title="Workspace unavailable"
      />
    </main>
  );
}
