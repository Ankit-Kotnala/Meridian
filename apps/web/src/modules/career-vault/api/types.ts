export type EvidenceState =
  "verified" | "confirmed" | "supported" | "inferred" | "unsupported";

export type SourceSpan = {
  digest: string;
  end: number;
  excerpt: string;
  id: string;
  page: number | null;
  start: number;
};

export type Provenance = {
  available: boolean;
  confidence: number | null;
  id: string;
  parserVersion: string | null;
  sourceDocumentId: string | null;
  sourceLabel: string;
  sourceRevision: number | null;
  sourceSnapshotId: string | null;
  sourceType: string;
  spans: SourceSpan[];
  userConfirmed: boolean;
};

export type ProfileConflict = {
  code: string;
  field: string;
  id: string;
  message: string;
  relatedEntityIds: string[];
  severity: "information" | "review";
};

export type CareerProfile = {
  accountPreferences: {
    displayName: string;
    email: string;
    industry: string | null;
    language: string;
    preferredLocation: string | null;
    seniority: string | null;
    targetRole: string | null;
    workModel: string | null;
  };
  createdAt: string;
  id: string;
  professionalHeadline: string;
  professionalSummary: string;
  updatedAt: string;
  version: number;
  workAuthorization: string;
};

export type CareerProfileUpdate = {
  professionalHeadline: string;
  professionalSummary: string;
  workAuthorization: string;
};

export type PersonalFactKind = "name" | "email" | "phone" | "location" | "link";

export type PersonalFactInput = {
  isPrimary: boolean;
  kind: PersonalFactKind;
  label: string | null;
  value: string;
};

export type PersonalFact = PersonalFactInput & {
  confirmation: "confirmed" | "needs_review";
  confirmedAt: string | null;
  createdAt: string;
  id: string;
  provenance: Provenance[];
  updatedAt: string;
  version: number;
};

export type Experience = {
  concurrentGroupId: string | null;
  conflicts: ProfileConflict[];
  current: boolean;
  createdAt: string;
  description: string;
  displayTitle: string | null;
  employer: string;
  employmentType: string | null;
  endDate: string | null;
  id: string;
  location: string | null;
  officialTitle: string;
  order: number;
  promotionGroupId: string | null;
  provenance: Provenance[];
  skillIds: string[];
  startDate: string;
  updatedAt: string;
  userConfirmed: boolean;
  version: number;
};

export type ExperienceInput = {
  current: boolean;
  description: string;
  displayTitle: string | null;
  employer: string;
  employmentType: string | null;
  endDate: string | null;
  groupWithExperienceId: string | null;
  location: string | null;
  officialTitle: string;
  skillIds: string[];
  startDate: string;
};

export type CareerItemKind =
  | "education"
  | "project"
  | "credential"
  | "publication"
  | "award"
  | "volunteering"
  | "language"
  | "portfolio_link";

export type CareerItemInput = {
  description: string;
  endDate: string | null;
  kind: CareerItemKind;
  organization: string | null;
  startDate: string | null;
  title: string;
  url: string | null;
};

export type CareerItem = CareerItemInput & {
  createdAt: string;
  id: string;
  order: number;
  provenance: Provenance[];
  updatedAt: string;
  userConfirmed: boolean;
  version: number;
};

export type CareerRelationship = {
  createdAt: string;
  experienceId: string;
  id: string;
  kind: "experience_project";
  projectId: string;
};

export type SkillInput = {
  category: string | null;
  name: string;
  proficiency: "learning" | "working" | "advanced" | "expert" | null;
};

export type Skill = SkillInput & {
  createdAt: string;
  id: string;
  order: number;
  provenance: Provenance[];
  updatedAt: string;
  userConfirmed: boolean;
  version: number;
};

export type ProfileImportChange = {
  conflict: string | null;
  currentValue: string | null;
  field: string;
  id: string;
  label: string;
  proposedValue: string;
  /**
   * How this value was settled during typed resume review. Every field passes
   * through review, so this records who last touched it rather than whether it
   * was reviewed at all.
   */
  reviewState: "confirmed" | "corrected" | "user_added";
  source: Provenance;
};

export type ProfileImportProposal = {
  changes: ProfileImportChange[];
  createdAt: string;
  id: string;
  sourceDocumentName: string;
  sourceAvailable: boolean;
  status: "pending" | "accepted" | "rejected";
  version: number;
};

export type ProfileImportQuestion = {
  code: "semantic_candidate_requires_review";
  missingFields: string[];
  semanticEntityId: string;
};

export type ProfileImportBatch = {
  appliedCount: number;
  proposals: ProfileImportProposal[];
  questions: ProfileImportQuestion[];
};

export type PageInfo = {
  hasMore: boolean;
  limit: number;
  nextCursor: string | null;
};

export type Page<T> = {
  data: T[];
  page: PageInfo;
};

export type EvidenceMetric = {
  attribution: "individual" | "shared" | "team";
  baseline: string | null;
  comparator: string | null;
  id: string | null;
  name: string;
  periodEnd: string | null;
  periodStart: string;
  precision: "approximate" | "exact";
  unit: string;
  value: string;
};

export type EvidenceAttachment = {
  createdAt: string;
  displayFilename: string;
  id: string;
  mediaType: string;
  safeErrorCode: string | null;
  sizeBytes: number;
  status: "uploading" | "scanning" | "ready" | "failed" | "deleting";
  updatedAt: string;
  version: number;
};

export type EvidenceUsage = {
  id: string;
  label: string;
  type: "experience" | "skill" | "requirement" | "output";
};

export type EvidenceHistoryEvent = {
  actorLabel: string;
  createdAt: string;
  fromState: EvidenceState | null;
  id: string;
  reason: string;
  toState: EvidenceState;
};

export type EvidenceConflict = {
  code:
    "date_mismatch" | "duplicate_claim" | "entity_mismatch" | "metric_mismatch";
  id: string;
  message: string;
  relatedEvidenceId: string;
  status: "open" | "resolved";
  version: number;
};

export type EvidenceItem = {
  archivedAt: string | null;
  attachments: EvidenceAttachment[];
  conflicts: EvidenceConflict[];
  createdAt: string;
  description: string;
  factualEligible: boolean;
  history: EvidenceHistoryEvent[];
  id: string;
  metrics: EvidenceMetric[];
  numericEligible: boolean;
  eligibilityReasons: string[];
  endDate: string | null;
  lifecycle: "active" | "archived";
  organizationOrProject: string | null;
  provenance: Provenance[];
  revision: number;
  startDate: string | null;
  state: EvidenceState;
  title: string;
  type: string;
  updatedAt: string;
  usage: EvidenceUsage[];
  userConfirmed: boolean;
  version: number;
};

export type EvidenceInput = {
  attachmentIds: string[];
  description: string;
  endDate: string | null;
  experienceIds: string[];
  metrics: Array<Omit<EvidenceMetric, "id">>;
  organizationOrProject: string | null;
  skillIds: string[];
  source: {
    blockId: string | null;
    documentId: string | null;
    end: number | null;
    page: number | null;
    snapshotId: string | null;
    sourceType: "attachment" | "manual" | "resume" | "url";
    start: number | null;
    url: string | null;
  };
  startDate: string | null;
  title: string;
  type: string;
};

export type EvidenceUpdate = Partial<
  Pick<
    EvidenceInput,
    | "description"
    | "endDate"
    | "experienceIds"
    | "metrics"
    | "organizationOrProject"
    | "skillIds"
    | "startDate"
    | "title"
  >
>;

export type EvidenceClaimUpdate = Pick<
  EvidenceInput,
  "description" | "endDate" | "organizationOrProject" | "startDate" | "title"
>;

export type EvidenceFilters = {
  after?: string;
  archived?: boolean;
  query?: string;
  state?: EvidenceState;
};

export type AchievementAnswers = {
  affected: string;
  changed: string;
  collaboration: string;
  delivered: string;
  measurement: string;
  methods: string;
  problem: string;
};

export type Achievement = {
  answers: AchievementAnswers;
  createdAt: string;
  employerId: string | null;
  evidenceId: string | null;
  id: string;
  metric: Omit<EvidenceMetric, "id"> | null;
  projectId: string | null;
  status: "draft" | "ready" | "converted" | "archived";
  title: string;
  updatedAt: string;
  version: number;
};

export type AchievementInput = Omit<
  Achievement,
  "createdAt" | "evidenceId" | "id" | "status" | "updatedAt" | "version"
>;

export type ReminderPreferences = {
  dayOfMonth: number | null;
  enabled: boolean;
  timezone: string;
  updatedAt: string;
  version: number;
};

export type AchievementConversion = {
  achievement: Achievement;
  evidence: EvidenceItem;
};

export type AttachmentUploadIntent = {
  attachmentId: string;
  expiresAt: string;
  headers: Record<string, string>;
  method: "PUT";
  uploadId: string;
  url: string;
};

export type AttachmentDownloadIntent = {
  expiresAt: string;
  url: string;
};
