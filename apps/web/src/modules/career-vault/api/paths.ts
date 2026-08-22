import type { GeneratedApiPath } from "@/shared/api/api-path";
import { buildApiQueryString } from "@/shared/api/api-query-string";

function path(value: string): GeneratedApiPath {
  if (!value.startsWith("/api/v1/") || /[\s#]/.test(value)) {
    throw new Error("Invalid Career Vault API path.");
  }
  return value as GeneratedApiPath;
}

function resource(base: string, id: string): GeneratedApiPath {
  if (!id) throw new Error("A resource identifier is required.");
  return path(`${base}/${encodeURIComponent(id)}`);
}

/**
 * Phase 3 paths stay centralized so they can be checked against generated
 * OpenAPI paths as the backend contract lands. Call sites never construct an
 * endpoint from user input beyond encoded resource identifiers and filters.
 */
export const careerVaultPaths = {
  achievement: (id: string) => resource("/api/v1/achievements", id),
  achievementConfirm: (id: string) =>
    path(`${resource("/api/v1/achievements", id)}/confirm`),
  achievementReminders: path("/api/v1/achievements/reminder-preferences"),
  achievements: path("/api/v1/achievements"),
  careerItem: (id: string) => resource("/api/v1/career-items", id),
  careerItemConfirm: (id: string) =>
    path(`${resource("/api/v1/career-items", id)}/confirm`),
  careerItems: path("/api/v1/career-items"),
  careerProfile: path("/api/v1/career-profile"),
  careerRelationship: (id: string) =>
    resource("/api/v1/career-relationships", id),
  careerRelationships: path("/api/v1/career-relationships"),
  evidence: path("/api/v1/evidence"),
  evidenceArchive: (id: string) =>
    path(`${resource("/api/v1/evidence", id)}/archive`),
  evidenceAttachment: (evidenceId: string, attachmentId: string) =>
    path(
      `${resource("/api/v1/evidence", evidenceId)}/attachments/${encodeURIComponent(attachmentId)}`,
    ),
  evidenceAttachmentFinalize: (evidenceId: string, uploadId: string) =>
    path(
      `${resource("/api/v1/evidence", evidenceId)}/attachments/${encodeURIComponent(uploadId)}/finalize`,
    ),
  evidenceAttachmentDownload: (evidenceId: string, attachmentId: string) =>
    path(
      `${resource("/api/v1/evidence", evidenceId)}/attachments/${encodeURIComponent(attachmentId)}/download`,
    ),
  evidenceAttachmentPresign: (id: string) =>
    path(`${resource("/api/v1/evidence", id)}/attachments/presign`),
  evidenceConfirm: (id: string) =>
    path(`${resource("/api/v1/evidence", id)}/confirm`),
  evidenceConflictResolve: (evidenceId: string, conflictId: string) =>
    path(
      `${resource("/api/v1/evidence", evidenceId)}/conflicts/${encodeURIComponent(conflictId)}/resolve`,
    ),
  evidenceItem: (id: string) => resource("/api/v1/evidence", id),
  evidenceRestore: (id: string) =>
    path(`${resource("/api/v1/evidence", id)}/restore`),
  evidenceUnsupported: (id: string) =>
    path(`${resource("/api/v1/evidence", id)}/unsupported`),
  evidenceUsage: (id: string) =>
    path(`${resource("/api/v1/evidence", id)}/usage`),
  experience: (id: string) => resource("/api/v1/experiences", id),
  experienceConfirm: (id: string) =>
    path(`${resource("/api/v1/experiences", id)}/confirm`),
  experienceReorder: path("/api/v1/experiences/reorder"),
  experiences: path("/api/v1/experiences"),
  skill: (id: string) => resource("/api/v1/skills", id),
  skillConfirm: (id: string) =>
    path(`${resource("/api/v1/skills", id)}/confirm`),
  skills: path("/api/v1/skills"),
  profileImportProposal: (id: string) =>
    resource("/api/v1/career-profile/semantic-import-proposals", id),
  profileImportProposalAccept: (id: string) =>
    path(
      `${resource("/api/v1/career-profile/semantic-import-proposals", id)}/accept`,
    ),
  profileImportProposalReject: (id: string) =>
    path(
      `${resource("/api/v1/career-profile/semantic-import-proposals", id)}/reject`,
    ),
  profileImportProposals: path(
    "/api/v1/career-profile/semantic-import-proposals",
  ),
  personalFact: (id: string) => resource("/api/v1/personal-facts", id),
  personalFactConfirm: (id: string) =>
    path(`${resource("/api/v1/personal-facts", id)}/confirm`),
  personalFactEnrich: (id: string) =>
    path(`${resource("/api/v1/personal-facts", id)}/enrich`),
  personalFacts: path("/api/v1/personal-facts"),
} as const;

export function withQuery(
  base: GeneratedApiPath,
  values: Record<string, boolean | string | undefined>,
): GeneratedApiPath {
  return path(`${base}${buildApiQueryString(values)}`);
}
