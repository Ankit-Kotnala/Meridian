"use client";

import { ErrorState } from "@/components/ui/async-state";

export default function DashboardError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
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
