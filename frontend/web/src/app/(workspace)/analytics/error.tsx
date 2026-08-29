"use client";

import { AnalyticsRouteError } from "@/modules/analytics";

export default function Error({ reset }: { reset: () => void }) {
  return <AnalyticsRouteError reset={reset} />;
}
