"use client";

import { ErrorState, LoadingSkeleton } from "@rezumi/ui";

function NetworkingRouteLoading({ label }: { label: string }) {
  return (
    <main
      aria-busy="true"
      className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8"
      id="main-content"
    >
      <h1 className="sr-only">{label}</h1>
      <LoadingSkeleton />
    </main>
  );
}

function NetworkingErrorShell({
  description,
  reset,
  title,
}: {
  description: string;
  reset: () => void;
  title: string;
}) {
  return (
    <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
      <ErrorState description={description} onRetry={reset} title={title} />
    </main>
  );
}

export function NetworkingLoading() {
  return <NetworkingRouteLoading label="Loading Networking" />;
}

export function NetworkingRouteError({ reset }: { reset: () => void }) {
  return (
    <NetworkingErrorShell
      description="The private Networking workspace could not be rendered. Try again; no outreach or external action was performed."
      reset={reset}
      title="Networking unavailable"
    />
  );
}

export function ContactLoading() {
  return <NetworkingRouteLoading label="Loading private contact" />;
}

export function ContactRouteError({ reset }: { reset: () => void }) {
  return (
    <NetworkingErrorShell
      description="The private contact view could not be rendered. Try again to load its current consent and local workspace state."
      reset={reset}
      title="Private contact unavailable"
    />
  );
}
