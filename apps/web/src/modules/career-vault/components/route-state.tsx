"use client";

import { ErrorState, LoadingSkeleton } from "@careeros/ui";

export function CareerVaultLoading() {
  return (
    <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
      <LoadingSkeleton />
    </main>
  );
}

export function CareerVaultRouteError({
  description,
  reset,
  title,
}: {
  description: string;
  reset: () => void;
  title: string;
}) {
  return (
    <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
      <ErrorState description={description} onRetry={reset} title={title} />
    </main>
  );
}
