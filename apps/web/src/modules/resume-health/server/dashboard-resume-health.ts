import { fillApiPath } from "@/shared/api/api-path";
import { serverApiFetch } from "@/shared/api/server-request";

import { parseDocument, parseDocumentList, parseReport } from "../api/contract-parsers";
import type { DocumentSummary } from "../api/types";

export type DashboardResumeHealthState =
  | { kind: "empty" }
  | { kind: "error" }
  | { filename: string; kind: "deleting" }
  | { filename: string; kind: "failed" }
  | { filename: string; kind: "processing" }
  | { documentId: string; filename: string; kind: "review" }
  | {
      documentId: string;
      filename: string;
      /** Reviewed semantics are ready to populate the career record. */
      kind: "importReady";
      snapshotId: string;
    }
  | {
      analysisId: string;
      disclaimer: string;
      /** Reviewed source the Career Record import reads its facts from. */
      documentId: string;
      filename: string;
      kind: "report";
      score: number | null;
      scoreBand: "developing" | "needsAttention" | "strong" | null;
      /** Snapshot frozen when the report was calculated. */
      snapshotId: string;
      /** Latest reviewed canonical snapshot, when import is allowed. */
      importSnapshotId?: string;
    };

export function resumeHealthImportSource(
  resumeHealth: DashboardResumeHealthState,
): { documentId: string; snapshotId: string } | undefined {
  if (resumeHealth.kind === "importReady") {
    return {
      documentId: resumeHealth.documentId,
      snapshotId: resumeHealth.snapshotId,
    };
  }
  if (resumeHealth.kind === "report") {
    return {
      documentId: resumeHealth.documentId,
      snapshotId: resumeHealth.importSnapshotId ?? resumeHealth.snapshotId,
    };
  }
  return undefined;
}

async function reviewedImportSource(
  document: DocumentSummary,
): Promise<{ documentId: string; snapshotId: string } | null> {
  const snapshotId = document.currentCanonicalResumeId;
  if (snapshotId == null) return null;
  const detailResponse = await serverApiFetch(
    fillApiPath("/api/v1/documents/{document_id}", {
      document_id: document.id,
    }),
  );
  if (!detailResponse.ok) return null;
  const detail = parseDocument(await detailResponse.json());
  const reviewState = detail.canonicalResume?.semanticReviewState;
  if (reviewState === "confirmed" || reviewState === "corrected") {
    return { documentId: document.id, snapshotId };
  }
  return null;
}

export async function dashboardResumeHealth(): Promise<DashboardResumeHealthState> {
  try {
    const response = await serverApiFetch("/api/v1/documents");
    if (!response.ok) return { kind: "error" };
    const documents = parseDocumentList(await response.json()).data;
    const document = documents[0];
    if (!document) return { kind: "empty" };
    if (document.status === "deleting") {
      return { filename: document.displayFilename, kind: "deleting" };
    }
    if (document.latestAnalysisId) {
      const reportResponse = await serverApiFetch(
        fillApiPath("/api/v1/resume-health/{analysis_id}", {
          analysis_id: document.latestAnalysisId,
        }),
      );
      if (!reportResponse.ok) return { kind: "error" };
      const report = parseReport(await reportResponse.json());
      const importSource = await reviewedImportSource(document);
      return {
        analysisId: report.id,
        disclaimer: report.disclaimer,
        documentId: report.documentId,
        filename: document.displayFilename,
        kind: "report",
        score: report.score,
        scoreBand: report.scoreBand,
        snapshotId: report.canonicalResumeId,
        ...(importSource === null
          ? {}
          : { importSnapshotId: importSource.snapshotId }),
      };
    }
    const importSource = await reviewedImportSource(document);
    if (importSource !== null) {
      return {
        documentId: importSource.documentId,
        filename: document.displayFilename,
        kind: "importReady",
        snapshotId: importSource.snapshotId,
      };
    }
    if (document.status === "reviewReady") {
      return {
        documentId: document.id,
        filename: document.displayFilename,
        kind: "review",
      };
    }
    if (document.status === "failed" || document.status === "cancelled") {
      return { filename: document.displayFilename, kind: "failed" };
    }
    return {
      filename: document.displayFilename,
      kind: "processing",
    };
  } catch {
    return { kind: "error" };
  }
}
