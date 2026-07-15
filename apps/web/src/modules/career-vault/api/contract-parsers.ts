import type {
  Achievement,
  AchievementConversion,
  AttachmentDownloadIntent,
  AttachmentUploadIntent,
  CareerProfile,
  EvidenceAttachment,
  EvidenceConflict,
  EvidenceHistoryEvent,
  EvidenceItem,
  EvidenceMetric,
  EvidenceState,
  EvidenceUsage,
  CareerItem,
  Skill,
  Experience,
  Page,
  ProfileConflict,
  ProfileImportProposal,
  Provenance,
  ReminderPreferences,
  SourceSpan,
} from "./types";

const evidenceStates = new Set<EvidenceState>([
  "verified",
  "confirmed",
  "supported",
  "inferred",
  "unsupported",
]);

function record(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`Invalid ${label} response.`);
  }
  return value as Record<string, unknown>;
}

function string(value: unknown, label: string, maximum = 20_000): string {
  if (typeof value !== "string" || value.length > maximum) {
    throw new Error(`Invalid ${label} response.`);
  }
  return value;
}

function nonEmpty(value: unknown, label: string, maximum = 500): string {
  const parsed = string(value, label, maximum);
  if (!parsed) throw new Error(`Invalid ${label} response.`);
  return parsed;
}

function nullableString(
  value: unknown,
  label: string,
  maximum = 20_000,
): string | null {
  return value === null || value === undefined
    ? null
    : string(value, label, maximum);
}

function nullableHttpUrl(value: unknown, label: string): string | null {
  const parsed = nullableString(value, label, 2_000);
  if (parsed === null) return null;
  let url: URL;
  try {
    url = new URL(parsed);
  } catch {
    throw new Error(`Invalid ${label} response.`);
  }
  if (
    !new Set(["http:", "https:"]).has(url.protocol) ||
    url.username ||
    url.password
  ) {
    throw new Error(`Invalid ${label} response.`);
  }
  return url.toString();
}

const PARTIAL_DATE = /^(19|20|21)\d{2}(?:-(0[1-9]|1[0-2]))?$/;

function partialDate(value: unknown, label: string): string {
  const parsed = nonEmpty(value, label, 7);
  if (!PARTIAL_DATE.test(parsed)) {
    throw new Error(`Invalid ${label} response.`);
  }
  return parsed;
}

function nullablePartialDate(value: unknown, label: string): string | null {
  return value === null || value === undefined
    ? null
    : partialDate(value, label);
}

function integer(value: unknown, label: string, maximum = 2_147_483_647) {
  if (
    typeof value !== "number" ||
    !Number.isInteger(value) ||
    value < 0 ||
    value > maximum
  ) {
    throw new Error(`Invalid ${label} response.`);
  }
  return value;
}

function boolean(value: unknown, label: string): boolean {
  if (typeof value !== "boolean") throw new Error(`Invalid ${label} response.`);
  return value;
}

function stringList(value: unknown, label: string, maximum = 100): string[] {
  if (
    !Array.isArray(value) ||
    value.length > maximum ||
    !value.every((item) => typeof item === "string" && item.length <= 250)
  ) {
    throw new Error(`Invalid ${label} response.`);
  }
  return value;
}

function list<T>(
  value: unknown,
  label: string,
  parser: (item: unknown) => T,
  maximum = 250,
): T[] {
  if (!Array.isArray(value) || value.length > maximum) {
    throw new Error(`Invalid ${label} response.`);
  }
  return value.map(parser);
}

function state(value: unknown, label = "evidence state"): EvidenceState {
  const normalized = nonEmpty(value, label, 30).toLowerCase() as EvidenceState;
  if (!evidenceStates.has(normalized)) {
    throw new Error(`Invalid ${label} response.`);
  }
  return normalized;
}

function span(value: unknown): SourceSpan {
  const candidate = record(value, "source span");
  return {
    digest: nonEmpty(candidate.digest, "source span digest", 80),
    end: integer(candidate.end, "source span end", 100_000_000),
    excerpt: string(candidate.excerpt ?? "", "source span excerpt", 2_000),
    id: nonEmpty(candidate.id, "source span ID", 100),
    page:
      candidate.page === null || candidate.page === undefined
        ? null
        : integer(candidate.page, "source span page", 100_000),
    start: integer(candidate.start, "source span start", 100_000_000),
  };
}

function provenance(value: unknown): Provenance {
  const candidate = record(value, "provenance");
  const confidence = candidate.confidence;
  if (
    confidence !== null &&
    confidence !== undefined &&
    (typeof confidence !== "number" || confidence < 0 || confidence > 100)
  ) {
    throw new Error("Invalid provenance confidence response.");
  }
  return {
    available: boolean(candidate.available, "source availability"),
    confidence: confidence === undefined ? null : (confidence as number | null),
    id: nonEmpty(candidate.id, "provenance ID", 100),
    parserVersion: nullableString(
      candidate.parserVersion,
      "parser version",
      100,
    ),
    sourceDocumentId: nullableString(
      candidate.sourceDocumentId,
      "source document ID",
      100,
    ),
    sourceLabel: nonEmpty(
      candidate.sourceLabel ?? candidate.sourceType,
      "source label",
      250,
    ),
    sourceRevision:
      candidate.sourceRevision === null ||
      candidate.sourceRevision === undefined
        ? null
        : integer(candidate.sourceRevision, "source revision"),
    sourceSnapshotId: nullableString(
      candidate.sourceSnapshotId,
      "source snapshot ID",
      100,
    ),
    sourceType: nonEmpty(candidate.sourceType, "source type", 80),
    spans: list(candidate.spans ?? [], "source spans", span, 100),
    userConfirmed: boolean(
      candidate.userConfirmed ?? false,
      "source confirmation",
    ),
  };
}

function conflict(value: unknown): ProfileConflict {
  const candidate = record(value, "profile conflict");
  const severity = nonEmpty(candidate.severity, "conflict severity", 20);
  if (!new Set(["information", "review"]).has(severity)) {
    throw new Error("Invalid conflict severity response.");
  }
  return {
    code: nonEmpty(candidate.code, "conflict code", 100),
    field: nonEmpty(candidate.field, "conflict field", 100),
    id: nonEmpty(candidate.id, "conflict ID", 100),
    message: nonEmpty(candidate.message, "conflict message", 1_000),
    relatedEntityIds: stringList(
      candidate.relatedEntityIds,
      "conflict related entity IDs",
      20,
    ),
    severity: severity as ProfileConflict["severity"],
  };
}

export function parseCareerProfile(value: unknown): CareerProfile {
  const candidate = record(value, "career profile");
  const account = record(candidate.accountPreferences, "account preferences");
  return {
    accountPreferences: {
      displayName: nonEmpty(account.displayName, "account display name", 160),
      email: nonEmpty(account.email, "account email", 320),
      industry: nullableString(account.industry, "account industry", 160),
      language: nonEmpty(account.language, "account language", 80),
      preferredLocation: nullableString(
        account.preferredLocation,
        "account preferred location",
        250,
      ),
      seniority: nullableString(account.seniority, "account seniority", 80),
      targetRole: nullableString(
        account.targetRole,
        "account target role",
        250,
      ),
      workModel: nullableString(account.workModel, "account work model", 80),
    },
    createdAt: nonEmpty(candidate.createdAt, "profile created date", 80),
    id: nonEmpty(candidate.id, "career profile ID", 100),
    professionalHeadline: string(
      candidate.professionalHeadline ?? "",
      "professional headline",
      240,
    ),
    professionalSummary: string(
      candidate.professionalSummary ?? "",
      "professional summary",
      5_000,
    ),
    updatedAt: nonEmpty(candidate.updatedAt, "profile updated date", 80),
    version: integer(candidate.version, "career profile version"),
    workAuthorization: string(
      candidate.workAuthorization ?? "",
      "work authorization",
      500,
    ),
  };
}

export function parseExperience(value: unknown): Experience {
  const candidate = record(value, "experience");
  return {
    concurrentGroupId: nullableString(
      candidate.concurrentGroupId,
      "concurrent group ID",
      100,
    ),
    conflicts: list(
      candidate.conflicts ?? [],
      "experience conflicts",
      conflict,
    ),
    current: boolean(
      candidate.current ?? !candidate.endDate,
      "current experience",
    ),
    createdAt: nonEmpty(candidate.createdAt, "experience created date", 80),
    description: string(candidate.description ?? "", "experience description"),
    displayTitle: nullableString(candidate.displayTitle, "display title", 250),
    employer: nonEmpty(candidate.employer, "experience employer", 250),
    employmentType: nullableString(
      candidate.employmentType,
      "employment type",
      80,
    ),
    endDate: nullablePartialDate(candidate.endDate, "experience end date"),
    id: nonEmpty(candidate.id, "experience ID", 100),
    location: nullableString(candidate.location, "experience location", 250),
    officialTitle: nonEmpty(candidate.officialTitle, "official title", 250),
    order: integer(candidate.order ?? 0, "experience order", 100_000),
    promotionGroupId: nullableString(
      candidate.promotionGroupId,
      "promotion group ID",
      100,
    ),
    provenance: list(
      candidate.provenance ?? [],
      "experience provenance",
      provenance,
    ),
    skillIds: stringList(candidate.skillIds ?? [], "experience skill IDs"),
    startDate: partialDate(candidate.startDate, "experience start date"),
    updatedAt: nonEmpty(candidate.updatedAt, "experience updated date", 80),
    userConfirmed: boolean(
      candidate.userConfirmed ?? false,
      "experience confirmation",
    ),
    version: integer(candidate.version, "experience version"),
  };
}

export function parseExperiences(value: unknown): Experience[] {
  if (Array.isArray(value)) {
    return list(value, "experiences", parseExperience, 500);
  }
  const candidate = record(value, "experience list");
  return list(candidate.data, "experiences", parseExperience, 500);
}

export function parseCareerItem(value: unknown): CareerItem {
  const candidate = record(value, "career item");
  const kind = nonEmpty(candidate.kind, "career item kind", 40);
  if (
    !new Set([
      "education",
      "project",
      "credential",
      "publication",
      "award",
      "volunteering",
      "language",
      "portfolio_link",
    ]).has(kind)
  ) {
    throw new Error("Invalid career item kind response.");
  }
  return {
    createdAt: nonEmpty(candidate.createdAt, "career item created date", 80),
    description: string(candidate.description ?? "", "career item description"),
    endDate: nullablePartialDate(candidate.endDate, "career item end date"),
    id: nonEmpty(candidate.id, "career item ID", 100),
    kind: kind as CareerItem["kind"],
    order: integer(candidate.order ?? 0, "career item order", 100_000),
    organization: nullableString(
      candidate.organization,
      "career item organization",
      300,
    ),
    provenance: list(
      candidate.provenance ?? [],
      "career item provenance",
      provenance,
    ),
    startDate: nullablePartialDate(
      candidate.startDate,
      "career item start date",
    ),
    title: nonEmpty(candidate.title, "career item title", 300),
    updatedAt: nonEmpty(candidate.updatedAt, "career item updated date", 80),
    url: nullableHttpUrl(candidate.url, "career item URL"),
    version: integer(candidate.version, "career item version"),
  };
}

export function parseCareerItems(value: unknown): CareerItem[] {
  const candidate = record(value, "career item list");
  return list(candidate.data, "career items", parseCareerItem, 500);
}

export function parseSkill(value: unknown): Skill {
  const candidate = record(value, "skill");
  const proficiency = nullableString(
    candidate.proficiency,
    "skill proficiency",
    30,
  );
  if (
    proficiency &&
    !new Set(["learning", "working", "advanced", "expert"]).has(proficiency)
  ) {
    throw new Error("Invalid skill proficiency response.");
  }
  return {
    category: nullableString(candidate.category, "skill category", 120),
    createdAt: nonEmpty(candidate.createdAt, "skill created date", 80),
    id: nonEmpty(candidate.id, "skill ID", 100),
    name: nonEmpty(candidate.name, "skill name", 160),
    order: integer(candidate.order ?? 0, "skill order", 100_000),
    proficiency: proficiency as Skill["proficiency"],
    updatedAt: nonEmpty(candidate.updatedAt, "skill updated date", 80),
    version: integer(candidate.version, "skill version"),
  };
}

export function parseSkills(value: unknown): Skill[] {
  const candidate = record(value, "skill list");
  return list(candidate.data, "skills", parseSkill, 500);
}

export function parseProfileImportProposal(
  value: unknown,
): ProfileImportProposal {
  const candidate = record(value, "profile import proposal");
  const status = nonEmpty(candidate.status, "proposal status", 30);
  if (!new Set(["pending", "accepted", "rejected"]).has(status)) {
    throw new Error("Invalid proposal status response.");
  }
  return {
    changes: list(candidate.changes, "proposal changes", (item) => {
      const change = record(item, "proposal change");
      return {
        conflict: nullableString(change.conflict, "proposal conflict", 1_000),
        currentValue: nullableString(
          change.currentValue,
          "proposal current value",
        ),
        field: nonEmpty(change.field, "proposal field", 100),
        id: nonEmpty(change.id, "proposal change ID", 100),
        label: nonEmpty(change.label, "proposal change label", 200),
        proposedValue: string(change.proposedValue, "proposal proposed value"),
        source: provenance(change.source),
      };
    }),
    createdAt: nonEmpty(candidate.createdAt, "proposal created date", 80),
    id: nonEmpty(candidate.id, "proposal ID", 100),
    sourceDocumentName: nonEmpty(
      candidate.sourceDocumentName,
      "proposal source document",
      250,
    ),
    status: status as ProfileImportProposal["status"],
    version: integer(candidate.version, "proposal version"),
  };
}

function metric(value: unknown): EvidenceMetric {
  const candidate = record(value, "evidence metric");
  const attribution = nonEmpty(candidate.attribution, "metric attribution", 30);
  const precision = nonEmpty(candidate.precision, "metric precision", 30);
  if (!new Set(["individual", "team", "shared"]).has(attribution)) {
    throw new Error("Invalid metric attribution response.");
  }
  if (!new Set(["exact", "approximate"]).has(precision)) {
    throw new Error("Invalid metric precision response.");
  }
  return {
    attribution: attribution as EvidenceMetric["attribution"],
    baseline:
      candidate.baseline === null || candidate.baseline === undefined
        ? null
        : String(candidate.baseline),
    comparator: nullableString(candidate.comparator, "metric comparator", 250),
    id: nullableString(candidate.id, "metric ID", 100),
    name: nonEmpty(candidate.name, "metric name", 160),
    periodEnd: nullablePartialDate(candidate.periodEnd, "metric period end"),
    periodStart: partialDate(candidate.periodStart, "metric period start"),
    precision: precision as EvidenceMetric["precision"],
    unit: nonEmpty(candidate.unit, "metric unit", 80),
    value: String(candidate.value ?? ""),
  };
}

function attachment(value: unknown): EvidenceAttachment {
  const candidate = record(value, "evidence attachment");
  const status = nonEmpty(candidate.status, "attachment status", 30);
  if (
    !new Set(["uploading", "scanning", "ready", "failed", "deleting"]).has(
      status,
    )
  ) {
    throw new Error("Invalid attachment status response.");
  }
  return {
    createdAt: nonEmpty(candidate.createdAt, "attachment created date", 80),
    displayFilename: nonEmpty(
      candidate.displayFilename,
      "attachment filename",
      250,
    ),
    id: nonEmpty(candidate.id, "attachment ID", 100),
    mediaType: nonEmpty(candidate.mediaType, "attachment media type", 150),
    safeErrorCode: nullableString(
      candidate.safeErrorCode,
      "attachment error code",
      100,
    ),
    sizeBytes: integer(candidate.sizeBytes, "attachment size", 100_000_000),
    status: status as EvidenceAttachment["status"],
    updatedAt: nonEmpty(candidate.updatedAt, "attachment updated date", 80),
    version: integer(candidate.version, "attachment version"),
  };
}

function evidenceConflict(value: unknown): EvidenceConflict {
  const candidate = record(value, "evidence conflict");
  return {
    code: nonEmpty(
      candidate.code,
      "evidence conflict code",
      40,
    ) as EvidenceConflict["code"],
    id: nonEmpty(candidate.id, "evidence conflict ID", 100),
    message: nonEmpty(candidate.message, "evidence conflict message", 1_000),
    relatedEvidenceId: nonEmpty(
      candidate.relatedEvidenceId,
      "related evidence ID",
      100,
    ),
    status: nonEmpty(
      candidate.status,
      "evidence conflict status",
      20,
    ) as EvidenceConflict["status"],
    version: integer(candidate.version, "evidence conflict version"),
  };
}

function usage(value: unknown): EvidenceUsage {
  const candidate = record(value, "evidence usage");
  const type = nonEmpty(candidate.type, "usage type", 30);
  if (!new Set(["experience", "skill", "requirement", "output"]).has(type)) {
    throw new Error("Invalid evidence usage type response.");
  }
  return {
    id: nonEmpty(candidate.id, "usage ID", 100),
    label: nonEmpty(candidate.label, "usage label", 500),
    type: type as EvidenceUsage["type"],
  };
}

function historyEvent(value: unknown): EvidenceHistoryEvent {
  const candidate = record(value, "evidence history");
  return {
    actorLabel: nonEmpty(candidate.actorLabel, "history actor", 100),
    createdAt: nonEmpty(candidate.createdAt, "history date", 80),
    fromState:
      candidate.fromState === null || candidate.fromState === undefined
        ? null
        : state(candidate.fromState),
    id: nonEmpty(candidate.id, "history ID", 100),
    reason: string(candidate.reason ?? "", "history reason", 1_000),
    toState: state(candidate.toState),
  };
}

export function parseEvidence(value: unknown): EvidenceItem {
  const candidate = record(value, "evidence");
  const parsedState = state(candidate.state);
  const metrics = list(candidate.metrics ?? [], "evidence metrics", metric, 50);
  const archivedAt = nullableString(candidate.archivedAt, "archive date", 80);
  return {
    archivedAt,
    attachments: list(
      candidate.attachments ?? [],
      "evidence attachments",
      attachment,
      50,
    ),
    conflicts: list(
      candidate.conflicts ?? [],
      "evidence conflicts",
      evidenceConflict,
      100,
    ),
    createdAt: nonEmpty(candidate.createdAt, "evidence created date", 80),
    description: string(candidate.description ?? "", "evidence description"),
    factualEligible: boolean(
      candidate.factualEligible,
      "factual generation eligibility",
    ),
    history: list(
      candidate.history ?? [],
      "evidence history",
      historyEvent,
      250,
    ),
    id: nonEmpty(candidate.id, "evidence ID", 100),
    eligibilityReasons: stringList(
      candidate.eligibilityReasons ?? [],
      "eligibility reasons",
      20,
    ),
    endDate: nullablePartialDate(candidate.endDate, "evidence end date"),
    lifecycle: nonEmpty(
      candidate.lifecycle,
      "evidence lifecycle",
      20,
    ) as EvidenceItem["lifecycle"],
    metrics,
    numericEligible: boolean(
      candidate.numericEligible,
      "numeric generation eligibility",
    ),
    organizationOrProject: nullableString(
      candidate.organizationOrProject,
      "evidence organization",
      500,
    ),
    provenance: list(
      candidate.provenance ?? [],
      "evidence provenance",
      provenance,
      100,
    ),
    revision: integer(candidate.revision, "evidence revision"),
    startDate: nullablePartialDate(candidate.startDate, "evidence start date"),
    state: parsedState,
    title: nonEmpty(candidate.title, "evidence title", 300),
    type: nonEmpty(candidate.type, "evidence type", 80),
    updatedAt: nonEmpty(candidate.updatedAt, "evidence updated date", 80),
    usage: list(candidate.usage ?? [], "evidence usage", usage, 250),
    userConfirmed: boolean(
      candidate.userConfirmed ?? false,
      "evidence confirmation",
    ),
    version: integer(candidate.version, "evidence version"),
  };
}

export function parseEvidencePage(value: unknown): Page<EvidenceItem> {
  const candidate = record(value, "evidence page");
  const page = record(candidate.page ?? {}, "evidence page information");
  return {
    data: list(candidate.data, "evidence items", parseEvidence),
    page: {
      hasMore: boolean(page.hasMore ?? false, "evidence has-more"),
      limit: integer(page.limit ?? 25, "evidence page limit", 100),
      nextCursor: nullableString(page.nextCursor, "evidence cursor", 2_000),
    },
  };
}

export function parseAchievement(value: unknown): Achievement {
  const candidate = record(value, "achievement");
  const answers = record(candidate.answers ?? {}, "achievement answers");
  const status = nonEmpty(candidate.status, "achievement status", 30);
  if (!new Set(["draft", "ready", "converted", "archived"]).has(status)) {
    throw new Error("Invalid achievement status response.");
  }
  const parsedMetric = candidate.metric ? metric(candidate.metric) : null;
  return {
    answers: {
      affected: string(answers.affected ?? "", "affected answer", 2_000),
      changed: string(answers.changed ?? "", "changed answer", 2_000),
      collaboration: string(
        answers.collaboration ?? "",
        "collaboration answer",
        2_000,
      ),
      delivered: string(answers.delivered ?? "", "delivered answer", 2_000),
      measurement: string(
        answers.measurement ?? "",
        "measurement answer",
        2_000,
      ),
      methods: string(answers.methods ?? "", "methods answer", 2_000),
      problem: string(answers.problem ?? "", "problem answer", 2_000),
    },
    createdAt: nonEmpty(candidate.createdAt, "achievement created date", 80),
    employerId: nullableString(candidate.employerId, "employer ID", 100),
    evidenceId: nullableString(candidate.evidenceId, "evidence ID", 100),
    id: nonEmpty(candidate.id, "achievement ID", 100),
    metric: parsedMetric
      ? {
          attribution: parsedMetric.attribution,
          baseline: parsedMetric.baseline,
          comparator: parsedMetric.comparator,
          name: parsedMetric.name,
          periodEnd: parsedMetric.periodEnd,
          periodStart: parsedMetric.periodStart,
          precision: parsedMetric.precision,
          unit: parsedMetric.unit,
          value: parsedMetric.value,
        }
      : null,
    projectId: nullableString(candidate.projectId, "project ID", 100),
    status: status as Achievement["status"],
    title: string(candidate.title ?? "", "achievement title", 300),
    updatedAt: nonEmpty(candidate.updatedAt, "achievement updated date", 80),
    version: integer(candidate.version, "achievement version"),
  };
}

export function parseAchievementPage(value: unknown): Page<Achievement> {
  const candidate = record(value, "achievement page");
  const page = record(candidate.page ?? {}, "achievement page information");
  return {
    data: list(candidate.data, "achievements", parseAchievement),
    page: {
      hasMore: boolean(page.hasMore ?? false, "achievement has-more"),
      limit: integer(page.limit ?? 25, "achievement page limit", 100),
      nextCursor: nullableString(page.nextCursor, "achievement cursor", 2_000),
    },
  };
}

export function parseReminderPreferences(value: unknown): ReminderPreferences {
  const candidate = record(value, "reminder preferences");
  return {
    dayOfMonth:
      candidate.dayOfMonth === null || candidate.dayOfMonth === undefined
        ? null
        : integer(candidate.dayOfMonth, "reminder day", 28),
    enabled: boolean(candidate.enabled, "reminder enabled"),
    timezone: nonEmpty(candidate.timezone, "reminder timezone", 100),
    updatedAt: nonEmpty(candidate.updatedAt, "reminder updated date", 80),
    version: integer(candidate.version, "reminder version"),
  };
}

export function parseAchievementConversion(
  value: unknown,
): AchievementConversion {
  const candidate = record(value, "achievement conversion");
  return {
    achievement: parseAchievement(candidate.achievement),
    evidence: parseEvidence(candidate.evidence),
  };
}

export function parseAttachmentUploadIntent(
  value: unknown,
): AttachmentUploadIntent {
  const candidate = record(value, "attachment upload intent");
  const headers = record(candidate.headers, "attachment upload headers");
  if (
    Object.values(headers).some((header) => typeof header !== "string") ||
    candidate.method !== "PUT"
  ) {
    throw new Error("Invalid attachment upload intent response.");
  }
  return {
    attachmentId: nonEmpty(candidate.attachmentId, "attachment ID", 100),
    expiresAt: nonEmpty(candidate.expiresAt, "attachment expiry", 80),
    headers: headers as Record<string, string>,
    method: "PUT",
    uploadId: nonEmpty(candidate.uploadId, "attachment upload ID", 100),
    url: nonEmpty(candidate.url, "attachment upload URL", 2_000),
  };
}

export function parseAttachmentDownloadIntent(
  value: unknown,
): AttachmentDownloadIntent {
  const candidate = record(value, "attachment download intent");
  return {
    expiresAt: nonEmpty(candidate.expiresAt, "attachment download expiry", 80),
    url: nonEmpty(candidate.url, "attachment download URL", 2_000),
  };
}
