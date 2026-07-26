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
  "semantic_entity_count",
  "semantic_field_count",
  "parsed_semantic_field_count",
  "source_anchored_field_count",
  "reviewed_semantic_field_count",
  "date_field_count",
  "precise_date_field_count",
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
  "source_anchor_coverage",
  "semantic_breadth",
  "semantic_review_coverage",
  "date_precision_coverage",
]);
const reportComponentKeys = new Set<unknown>([
  "machine_readability",
  "recruiter_clarity",
  "content_impact",
  "achievement_strength",
  "structure",
  "consistency_truth",
]);
const semanticKinds = new Set<unknown>([
  "contact",
  "experience",
  "education",
  "project",
  "skill",
  "certification",
]);
const semanticFieldNames: Record<string, Set<unknown>> = {
  contact: new Set(["name", "email", "phone", "location", "link"]),
  experience: new Set([
    "employer",
    "title",
    "start_date",
    "end_date",
    "location",
    "employment_type",
    "description",
    "achievement",
  ]),
  education: new Set([
    "institution",
    "degree",
    "field",
    "start_date",
    "end_date",
    "location",
  ]),
  project: new Set([
    "name",
    "description",
    "start_date",
    "end_date",
    "skill",
    "link",
  ]),
  skill: new Set(["name", "category"]),
  certification: new Set([
    "name",
    "issuer",
    "issued_date",
    "expires_date",
    "credential_id",
    "link",
  ]),
};
const semanticFieldTypes = new Set<unknown>([
  "text",
  "email",
  "phone",
  "url",
  "date",
  "bullet",
]);
const semanticReviewStates = new Set<unknown>([
  "unreviewed",
  "confirmed",
  "corrected",
  "user_added",
  "removed",
]);
const datePrecisions = new Set<unknown>(["day", "month", "year", "unknown"]);

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

function semanticAnchor(value: unknown): Record<string, unknown> {
  const candidate = record(value, "semantic source anchor");
  if (
    typeof candidate.blockId !== "string" ||
    !boundedInteger(candidate.page, 10_000) ||
    candidate.page < 1 ||
    !boundedInteger(candidate.start, 100_000_000) ||
    !boundedInteger(candidate.end, 100_000_000) ||
    candidate.end <= candidate.start ||
    typeof candidate.sourceSha256 !== "string" ||
    !/^[a-f0-9]{64}$/.test(candidate.sourceSha256) ||
    typeof candidate.excerpt !== "string" ||
    candidate.excerpt.length > 240
  ) {
    throw new Error("Invalid semantic source anchor response.");
  }
  return candidate;
}

function semanticField(value: unknown): Record<string, unknown> {
  const candidate = record(value, "semantic field");
  if (
    typeof candidate.id !== "string" ||
    !boundedText(candidate.name, 80) ||
    !semanticFieldTypes.has(candidate.fieldType) ||
    !boundedText(candidate.value, 10_000) ||
    !boundedInteger(candidate.confidence, 100) ||
    !semanticReviewStates.has(candidate.reviewState) ||
    !Array.isArray(candidate.anchors) ||
    candidate.anchors.length > 100 ||
    (candidate.fieldType === "date") !==
      datePrecisions.has(candidate.datePrecision) ||
    (candidate.fieldType !== "date" && candidate.datePrecision !== null)
  ) {
    throw new Error("Invalid semantic field response.");
  }
  const anchors = candidate.anchors.map(semanticAnchor);
  if (
    new Set(
      anchors.map(
        (anchor) =>
          `${String(anchor.blockId)}:${String(anchor.page)}:${String(anchor.start)}:${String(anchor.end)}`,
      ),
    ).size !== anchors.length ||
    (candidate.reviewState === "user_added" && anchors.length > 0) ||
    (candidate.reviewState !== "user_added" &&
      candidate.reviewState !== "removed" &&
      anchors.length === 0)
  ) {
    throw new Error("Invalid semantic field response.");
  }
  return candidate;
}

function semanticEntity(value: unknown): Record<string, unknown> {
  const candidate = record(value, "semantic entity");
  if (
    typeof candidate.id !== "string" ||
    !semanticKinds.has(candidate.kind) ||
    !semanticReviewStates.has(candidate.reviewState) ||
    (candidate.sourceSectionId !== null &&
      typeof candidate.sourceSectionId !== "string") ||
    !Array.isArray(candidate.fields) ||
    candidate.fields.length === 0 ||
    candidate.fields.length > 250
  ) {
    throw new Error("Invalid semantic entity response.");
  }
  const fields = candidate.fields.map(semanticField);
  const allowedNames = semanticFieldNames[String(candidate.kind)];
  if (
    !allowedNames ||
    fields.some(
      (field) =>
        !allowedNames.has(field.name) ||
        !semanticNameAllowsType(String(field.name), String(field.fieldType)),
    ) ||
    new Set(fields.map((field) => field.id)).size !== fields.length ||
    (candidate.reviewState === "user_added" &&
      (candidate.sourceSectionId !== null ||
        fields.some(
          (field) =>
            field.reviewState !== "user_added" &&
            field.reviewState !== "removed",
        ))) ||
    (candidate.reviewState === "removed" &&
      fields.some((field) => field.reviewState !== "removed"))
  ) {
    throw new Error("Invalid semantic entity response.");
  }
  return candidate;
}

function semanticNameAllowsType(name: string, fieldType: string): boolean {
  if (name === "description") {
    return fieldType === "text" || fieldType === "bullet";
  }
  if (name === "achievement") return fieldType === "bullet";
  if (name === "email") return fieldType === "email";
  if (name === "phone") return fieldType === "phone";
  if (name === "link") return fieldType === "url";
  if (name.includes("date")) return fieldType === "date";
  return fieldType === "text";
}

function parserWarning(value: unknown): Record<string, unknown> {
  const candidate = record(value, "parser warning");
  if (
    !boundedText(candidate.code, 160) ||
    !boundedText(candidate.message, 500) ||
    (candidate.fieldId !== null && typeof candidate.fieldId !== "string")
  ) {
    throw new Error("Invalid parser warning response.");
  }
  return candidate;
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
    candidate.featureContributions.length > 7
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
  if (candidate.canonicalResume !== null) {
    parseCanonical(candidate.canonicalResume);
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
    !Array.isArray(candidate.warnings) ||
    !Array.isArray(candidate.semanticEntities) ||
    !Array.isArray(candidate.semanticWarnings) ||
    typeof candidate.legacyUpgradeRequired !== "boolean"
  ) {
    throw new Error("Invalid canonical resume response.");
  }
  const semanticEntities = candidate.semanticEntities.map(semanticEntity);
  candidate.semanticWarnings.map(parserWarning);
  candidate.warnings.map(parserWarning);
  const legacy = candidate.legacyUpgradeRequired;
  if (
    new Set(semanticEntities.map((entity) => entity.id)).size !==
      semanticEntities.length ||
    (legacy &&
      (candidate.semanticSchemaVersion !== null ||
        candidate.semanticParserVersion !== null ||
        candidate.semanticReviewState !== null ||
        semanticEntities.length > 0)) ||
    (!legacy &&
      (!boundedText(candidate.semanticSchemaVersion, 80) ||
        !boundedText(candidate.semanticParserVersion, 80) ||
        !semanticReviewStates.has(candidate.semanticReviewState)))
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
    candidate.featureValues.length > 24 ||
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
