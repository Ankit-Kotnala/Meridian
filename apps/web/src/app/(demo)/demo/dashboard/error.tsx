"use client";

import { ErrorState } from "@careeros/ui";

export default function DashboardDemoError({ reset }: { reset: () => void }) {
  return (
    <main className="mx-auto max-w-[98rem] p-6" id="main-content">
      <ErrorState
        description="The fictional dashboard preview could not be rendered. No user data was affected."
        onRetry={reset}
        title="Dashboard preview unavailable"
      />
    </main>
  );
}
