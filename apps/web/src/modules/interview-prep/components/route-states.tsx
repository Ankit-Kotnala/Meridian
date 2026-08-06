"use client";

import { ErrorState, LoadingSkeleton } from "@rezumi/ui";

function InterviewRouteLoading({ label }: { label: string }) {
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

function InterviewRouteError({
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

export function InterviewPrepLoading() {
  return <InterviewRouteLoading label="Loading Interview Prep" />;
}

export function InterviewPrepRouteError({ reset }: { reset: () => void }) {
  return (
    <InterviewRouteError
      description="The Interview Prep workspace could not be rendered. Try again; your source applications and Career Record evidence are unchanged."
      reset={reset}
      title="Interview Prep unavailable"
    />
  );
}

export function StarStoryLoading() {
  return <InterviewRouteLoading label="Loading STAR story" />;
}

export function StarStoryRouteError({ reset }: { reset: () => void }) {
  return (
    <InterviewRouteError
      description="The STAR story view could not be rendered. Try again to load its current provenance-pinned version."
      reset={reset}
      title="STAR story unavailable"
    />
  );
}

export function InterviewSessionLoading() {
  return <InterviewRouteLoading label="Loading interview session" />;
}

export function InterviewSessionRouteError({ reset }: { reset: () => void }) {
  return (
    <InterviewRouteError
      description="The private interview session could not be rendered. Try again to load its current bounded context."
      reset={reset}
      title="Interview session unavailable"
    />
  );
}
