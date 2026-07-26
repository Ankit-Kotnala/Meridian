import type { Metadata } from "next";
import { notFound } from "next/navigation";

import {
  InterviewSessionDetailView,
  isInterviewPrepId,
} from "@/modules/interview-prep";

export const metadata: Metadata = { title: "Interview session" };

export default async function InterviewSessionPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  if (!isInterviewPrepId(sessionId)) notFound();
  return <InterviewSessionDetailView sessionId={sessionId} />;
}
