import type { Metadata } from "next";

import { InterviewPrepView } from "@/modules/interview-prep";

export const metadata: Metadata = { title: "Interview Prep" };

export default function InterviewPrepPage() {
  return <InterviewPrepView />;
}
