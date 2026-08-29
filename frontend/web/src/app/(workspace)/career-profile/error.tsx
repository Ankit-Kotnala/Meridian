"use client";

import { CareerVaultRouteError } from "@/modules/career-vault";

export default function CareerProfileError({ reset }: { reset: () => void }) {
  return (
    <CareerVaultRouteError
      description="Your owned career profile could not be displayed. No career record was changed."
      reset={reset}
      title="Career Profile unavailable"
    />
  );
}
