"use client";

import { CareerVaultRouteError } from "@/modules/career-vault";

export default function ProfileImportReviewError({
  reset,
}: {
  reset: () => void;
}) {
  return (
    <CareerVaultRouteError
      description="This import proposal could not be displayed. No proposed change was applied."
      reset={reset}
      title="Import proposal unavailable"
    />
  );
}
