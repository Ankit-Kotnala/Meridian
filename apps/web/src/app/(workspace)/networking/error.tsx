"use client";

import { NetworkingRouteError } from "@/modules/networking";

export default function Error({ reset }: { reset: () => void }) {
  return <NetworkingRouteError reset={reset} />;
}
