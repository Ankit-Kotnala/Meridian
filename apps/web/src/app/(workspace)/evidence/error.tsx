"use client";

import { CareerVaultRouteError } from "@/modules/career-vault";

export default function EvidenceVaultError({ reset }: { reset: () => void }) {
  return (
    <CareerVaultRouteError
      description="Your private Evidence Vault could not be displayed. No evidence was changed."
      reset={reset}
      title="Evidence Vault unavailable"
    />
  );
}
