import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AutoImportRunner } from "@/modules/career-vault";
import {
  isResourceId,
  reportImportSource,
  ResumeHealthReportView,
} from "@/modules/resume-health";

export const metadata: Metadata = { title: "Resume Health report" };

export default async function AccountReportPage({
  params,
}: {
  params: Promise<{ analysisId: string }>;
}) {
  const { analysisId } = await params;
  if (!isResourceId(analysisId)) notFound();
  const importSource = await reportImportSource(analysisId);
  return (
    <ResumeHealthReportView
      access="account"
      analysisId={analysisId}
      autoImport={
        importSource === undefined ? undefined : (
          <AutoImportRunner
            documentId={importSource.documentId}
            snapshotId={importSource.snapshotId}
          />
        )
      }
    />
  );
}
