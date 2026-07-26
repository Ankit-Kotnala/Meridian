"use client";

import { StarStoryRouteError } from "@/modules/interview-prep";

export default function Error({ reset }: { reset: () => void }) {
  return <StarStoryRouteError reset={reset} />;
}
