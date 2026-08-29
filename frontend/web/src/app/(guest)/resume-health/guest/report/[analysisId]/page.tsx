import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { isResourceId, ResumeHealthReportView } from "@/modules/resume-health";

export const metadata: Metadata = { title: "Guest Resume Health report" };

export default async function GuestReportPage({
  params,
}: {
  params: Promise<{ analysisId: string }>;
}) {
  const { analysisId } = await params;
  if (!isResourceId(analysisId)) notFound();
  return <ResumeHealthReportView access="guest" analysisId={analysisId} />;
}
