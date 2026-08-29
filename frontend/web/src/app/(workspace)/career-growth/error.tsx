"use client";

import { CareerGrowthRouteError } from "@/modules/career-growth";

export default function Error({ reset }: { reset: () => void }) {
  return <CareerGrowthRouteError reset={reset} />;
}
