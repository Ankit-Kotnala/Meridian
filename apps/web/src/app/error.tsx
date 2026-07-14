"use client";

import { ErrorState } from "@careeros/ui";

export default function ErrorPage({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="site-container py-20" id="main-content">
      <ErrorState onRetry={reset} />
    </main>
  );
}
