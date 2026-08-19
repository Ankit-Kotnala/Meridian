import { fillApiPath } from "@/shared/api/api-path";
import { serverApiFetch } from "@/shared/api/server-request";

import { parseDocumentList, parseReport } from "../api/contract-parsers";

export type DashboardResumeHealthState =
  | { kind: "empty" }
  | { kind: "error" }
  | { filename: string; kind: "deleting" }
  | { filename: string; kind: "failed" }
  | { filename: string; kind: "processing" }
  | { documentId: string; filename: string; kind: "review" }
  | {
      analysisId: string;
      disclaimer: string;
      /** Reviewed source the Career Record import reads its facts from. */
      documentId: string;
      filename: string;
      kind: "report";
      score: number | null;
      scoreBand: "developing" | "needsAttention" | "strong" | null;
      snapshotId: string;
    };

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
      return {
        analysisId: report.id,
        disclaimer: report.disclaimer,
        documentId: report.documentId,
        filename: document.displayFilename,
        kind: "report",
        score: report.score,
        scoreBand: report.scoreBand,
        snapshotId: report.canonicalResumeId,
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
