import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { isResourceId, ResumeHealthReportView } from "@/modules/resume-health";

export const metadata: Metadata = { title: "Resume Health report" };

export default async function AccountReportPage({
  params,
}: {
  params: Promise<{ analysisId: string }>;
}) {
  const { analysisId } = await params;
  if (!isResourceId(analysisId)) notFound();
  return <ResumeHealthReportView access="account" analysisId={analysisId} />;
}
