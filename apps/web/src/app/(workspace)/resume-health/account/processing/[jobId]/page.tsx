import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { isResourceId, ProcessingView } from "@/modules/resume-health";

export const metadata: Metadata = { title: "Processing resume" };

export default async function AccountProcessingPage({
  params,
}: {
  params: Promise<{ jobId: string }>;
}) {
  const { jobId } = await params;
  if (!isResourceId(jobId)) notFound();
  return <ProcessingView access="account" jobId={jobId} />;
}
