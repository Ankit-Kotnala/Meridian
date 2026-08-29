"use client";

import { CareerVaultRouteError } from "@/modules/career-vault";

export default function EvidenceDetailError({ reset }: { reset: () => void }) {
  return (
    <CareerVaultRouteError
      description="This evidence item could not be displayed. No evidence was changed."
      reset={reset}
      title="Evidence unavailable"
    />
  );
}
