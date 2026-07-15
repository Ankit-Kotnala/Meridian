import type {
  CanonicalResume,
  ClaimGuestDocument,
  DocumentDetail,
  DocumentList,
  FinalizeUpload,
  JobAccepted,
  PlainText,
  ProcessingJob,
  ReadingOrder,
  ResumeHealthReport,
  UploadIntent,
  UploadPolicy,
} from "./types";

const reportFeatureKinds = new Set<unknown>(["count", "boolean", "percentage"]);
const reportFeatureKeys = new Set<unknown>([
  "text_characters",
  "page_count",
  "image_only",
  "section_count",
  "recognized_section_count",
  "block_count",
  "concise_block_count",
  "bullet_count",
  "action_bullet_count",
  "outcome_bullet_count",
  "duplicate_block_count",
  "chronology_signal_count",
  "warning_count",
  "reading_order_violation_count",
  "average_confidence_basis_points",
]);
const reportContributionKeys = new Set<unknown>([
  "searchable_text",
  "parser_confidence",
  "reading_order_integrity",
  "recognized_section_ratio",
  "concise_block_ratio",
  "section_breadth",
  "chronology_coverage",
  "action_bullet_ratio",
  "outcome_bullet_ratio",
  "duplicate_content_integrity",
  "page_fit",
  "parser_warning_integrity",
]);
const reportComponentKeys = new Set<unknown>([
  "machine_readability",
  "recruiter_clarity",
  "content_impact",
  "achievement_strength",
  "structure",
  "consistency_truth",
]);

function record(value: unknown, name: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`Invalid ${name} response.`);
  }
  return value as Record<string, unknown>;
}

function strings(value: unknown): value is string[] {
  return (
    Array.isArray(value) && value.every((item) => typeof item === "string")
  );
}

function boundedInteger(value: unknown, maximum: number): value is number {
  return (
    typeof value === "number" &&
    Number.isInteger(value) &&
    value >= 0 &&
    value <= maximum
  );
}

function boundedText(value: unknown, maximum: number): value is string {
  return (
    typeof value === "string" && value.length > 0 && value.length <= maximum
  );
}

function featureValue(value: unknown): Record<string, unknown> {
  const candidate = record(value, "Resume Health feature value");
  const validKind = reportFeatureKinds.has(candidate.kind);
  const validRawValue =
    candidate.kind === "boolean"
      ? typeof candidate.rawValue === "boolean"
      : boundedInteger(
          candidate.rawValue,
          candidate.kind === "percentage" ? 10_000 : 100_000_000,
        );
  if (
    !reportFeatureKeys.has(candidate.key) ||
    !boundedText(candidate.label, 80) ||
    !validKind ||
    !validRawValue ||
    !boundedText(candidate.displayValue, 40)
  ) {
    throw new Error("Invalid Resume Health feature value response.");
  }
  return candidate;
}

function featureContribution(value: unknown): Record<string, unknown> {
  const candidate = record(value, "Resume Health feature contribution");
  if (
    !reportContributionKeys.has(candidate.key) ||
    !boundedText(candidate.label, 80) ||
    !boundedInteger(candidate.score, 100) ||
    !boundedInteger(candidate.rawScoreBasisPoints, 10_000) ||
    !boundedInteger(candidate.weight, 100) ||
    !boundedInteger(candidate.rawWeightBasisPoints, 10_000) ||
    !boundedInteger(candidate.contribution, 100) ||
    !boundedInteger(candidate.rawContributionBasisPoints, 10_000)
  ) {
    throw new Error("Invalid Resume Health feature contribution response.");
  }
  return candidate;
}

function reportComponent(value: unknown): Record<string, unknown> {
  const candidate = record(value, "Resume Health component");
  if (
    !reportComponentKeys.has(candidate.key) ||
    !boundedText(candidate.label, 80) ||
    !boundedInteger(candidate.score, 100) ||
    !boundedInteger(candidate.rawScoreBasisPoints, 10_000) ||
    !boundedInteger(candidate.weight, 100) ||
    !boundedInteger(candidate.contribution, 100) ||
    !boundedInteger(candidate.rawContributionBasisPoints, 10_000) ||
    !boundedText(candidate.explanation, 2_000) ||
    !Array.isArray(candidate.featureContributions) ||
    candidate.featureContributions.length > 4
  ) {
    throw new Error("Invalid Resume Health component response.");
  }
  const contributions = candidate.featureContributions.map(featureContribution);
  if (
    new Set(contributions.map((contribution) => contribution.key)).size !==
    contributions.length
  ) {
    throw new Error("Invalid Resume Health component response.");
  }
  return candidate;
}

function job(value: unknown): ProcessingJob {
  const candidate = record(value, "processing job");
  if (
    typeof candidate.id !== "string" ||
    typeof candidate.documentId !== "string" ||
    typeof candidate.jobType !== "string" ||
    typeof candidate.status !== "string" ||
    typeof candidate.stage !== "string" ||
    typeof candidate.attempts !== "number" ||
    typeof candidate.createdAt !== "string" ||
    typeof candidate.updatedAt !== "string" ||
    (candidate.progress !== null && typeof candidate.progress !== "number")
  ) {
    throw new Error("Invalid processing job response.");
  }
  return candidate as unknown as ProcessingJob;
}

export function parseUploadPolicy(value: unknown): UploadPolicy {
  const candidate = record(value, "upload policy");
  if (
    !strings(candidate.acceptedMediaTypes) ||
    typeof candidate.maxBytes !== "number" ||
    typeof candidate.maxPages !== "number" ||
    typeof candidate.guestRetentionHours !== "number" ||
    typeof candidate.uploadIntentTtlSeconds !== "number"
  ) {
    throw new Error("Invalid upload policy response.");
  }
  return candidate as unknown as UploadPolicy;
}

export function parseUploadIntent(value: unknown): UploadIntent {
  const candidate = record(value, "upload intent");
  if (
    typeof candidate.uploadId !== "string" ||
    typeof candidate.url !== "string" ||
    candidate.method !== "PUT" ||
    typeof candidate.headers !== "object" ||
    candidate.headers === null ||
    typeof candidate.expiresAt !== "string"
  ) {
    throw new Error("Invalid upload intent response.");
  }
  return candidate as unknown as UploadIntent;
}

export function parseFinalizeUpload(value: unknown): FinalizeUpload {
  const candidate = record(value, "upload finalization");
  if (typeof candidate.documentId !== "string") {
    throw new Error("Invalid upload finalization response.");
  }
  return { ...candidate, job: job(candidate.job) } as unknown as FinalizeUpload;
}

export function parseJob(value: unknown): ProcessingJob {
  return job(value);
}

export function parseJobAccepted(value: unknown): JobAccepted {
  const candidate = record(value, "accepted job");
  return { job: job(candidate.job) };
}

export function parseDocumentList(value: unknown): DocumentList {
  const candidate = record(value, "document list");
  if (!Array.isArray(candidate.data)) {
    throw new Error("Invalid document list response.");
  }
  for (const item of candidate.data) {
    const document = record(item, "document");
    if (
      typeof document.id !== "string" ||
      typeof document.displayFilename !== "string" ||
      typeof document.status !== "string" ||
      typeof document.version !== "number" ||
      typeof document.createdAt !== "string"
    ) {
      throw new Error("Invalid document list response.");
    }
  }
  return candidate as unknown as DocumentList;
}

export function parseDocument(value: unknown): DocumentDetail {
  const candidate = record(value, "document");
  if (
    typeof candidate.id !== "string" ||
    typeof candidate.displayFilename !== "string" ||
    typeof candidate.status !== "string" ||
    typeof candidate.version !== "number"
  ) {
    throw new Error("Invalid document response.");
  }
  return candidate as unknown as DocumentDetail;
}

export function parseCanonical(value: unknown): CanonicalResume {
  const candidate = record(value, "canonical resume");
  if (
    typeof candidate.id !== "string" ||
    typeof candidate.documentId !== "string" ||
    typeof candidate.version !== "number" ||
    !Array.isArray(candidate.sections) ||
    !Array.isArray(candidate.warnings)
  ) {
    throw new Error("Invalid canonical resume response.");
  }
  return candidate as unknown as CanonicalResume;
}

export function parsePlainText(value: unknown): PlainText {
  const candidate = record(value, "plain text");
  if (
    typeof candidate.documentId !== "string" ||
    typeof candidate.text !== "string" ||
    typeof candidate.truncated !== "boolean"
  ) {
    throw new Error("Invalid plain text response.");
  }
  return candidate as unknown as PlainText;
}

export function parseReadingOrder(value: unknown): ReadingOrder {
  const candidate = record(value, "reading order");
  if (
    typeof candidate.documentId !== "string" ||
    !Array.isArray(candidate.blocks)
  ) {
    throw new Error("Invalid reading order response.");
  }
  return candidate as unknown as ReadingOrder;
}

export function parseReport(value: unknown): ResumeHealthReport {
  const candidate = record(value, "Resume Health report");
  if (
    typeof candidate.id !== "string" ||
    typeof candidate.documentId !== "string" ||
    typeof candidate.status !== "string" ||
    !Array.isArray(candidate.components) ||
    candidate.components.length > 6 ||
    !Array.isArray(candidate.featureValues) ||
    candidate.featureValues.length > 15 ||
    !Array.isArray(candidate.findings) ||
    !strings(candidate.warnings) ||
    typeof candidate.disclaimer !== "string" ||
    typeof candidate.engineVersion !== "string" ||
    typeof candidate.configurationVersion !== "string" ||
    !boundedText(candidate.featureSchemaVersion, 80)
  ) {
    throw new Error("Invalid Resume Health report response.");
  }
  const featureValues = candidate.featureValues.map(featureValue);
  const components = candidate.components.map(reportComponent);
  if (
    new Set(featureValues.map((feature) => feature.key)).size !==
      featureValues.length ||
    new Set(components.map((component) => component.key)).size !==
      components.length
  ) {
    throw new Error("Invalid Resume Health report response.");
  }
  return candidate as unknown as ResumeHealthReport;
}

export function parseClaim(value: unknown): ClaimGuestDocument {
  const candidate = record(value, "guest claim");
  if (
    typeof candidate.documentId !== "string" ||
    candidate.accessMode !== "account"
  ) {
    throw new Error("Invalid guest claim response.");
  }
  return candidate as unknown as ClaimGuestDocument;
}
