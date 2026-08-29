"use client";

import { InterviewPrepRouteError } from "@/modules/interview-prep";

export default function Error({ reset }: { reset: () => void }) {
  return <InterviewPrepRouteError reset={reset} />;
}
