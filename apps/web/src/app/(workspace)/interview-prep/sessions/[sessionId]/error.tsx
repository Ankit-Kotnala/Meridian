"use client";

import { InterviewSessionRouteError } from "@/modules/interview-prep";

export default function Error({ reset }: { reset: () => void }) {
  return <InterviewSessionRouteError reset={reset} />;
}
