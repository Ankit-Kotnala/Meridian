"use client";

import { ErrorState } from "@rezumi/ui";

export default function SettingsError({ reset }: { reset: () => void }) {
  return <ErrorState onRetry={reset} title="Settings unavailable" />;
}
