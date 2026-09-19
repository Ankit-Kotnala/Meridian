import type { ResumeSourceOptions } from "../api/types";

export type ResumeBuilderReadinessStatus =
  | "loading"
  | "ready"
  | "blocked"
  | "error";

export type ResumeBuilderReadinessStep = {
  actionLabel: string;
  complete: boolean;
  description: string;
  href: string;
  id: "profile" | "evidence" | "confirm";
  title: string;
};

export type ResumeBuilderReadinessSnapshot = {
  confirmedEvidenceCount: number;
  draftEvidenceCount: number;
  experienceCount: number;
  skillCount: number;
  sourceOptions?: ResumeSourceOptions;
  status: ResumeBuilderReadinessStatus;
  steps: ResumeBuilderReadinessStep[];
  summary?: string;
};

type EvidenceRecord = {
  state?: string;
};

type ListPayload = {
  data?: unknown[];
};

function asList(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : null;
}

function readListCount(payload: ListPayload | null): number {
  return asList(payload?.data).length;
}

function readEvidenceCounts(payload: ListPayload | null): {
  confirmed: number;
  draft: number;
  total: number;
} {
  const records = asList(payload?.data).map((item) => asRecord(item));
  const states = records.map((record) =>
    typeof record?.state === "string" ? record.state : "",
  );
  const confirmed = states.filter(
    (state) => state === "confirmed" || state === "verified",
  ).length;
  const draft = states.filter((state) => state === "supported").length;
  return { confirmed, draft, total: records.length };
}

export function buildReadinessSnapshot(input: {
  evidencePayload: ListPayload | null;
  experiencesPayload: ListPayload | null;
  skillsPayload: ListPayload | null;
  sourceError?: string;
  sourceOptions?: ResumeSourceOptions;
}): ResumeBuilderReadinessSnapshot {
  const skillCount = readListCount(input.skillsPayload);
  const experienceCount = readListCount(input.experiencesPayload);
  const evidenceCounts = readEvidenceCounts(input.evidencePayload);
  const eligibleEvidenceCount =
    input.sourceOptions?.sourceEvidenceIds.length ?? 0;

  const profileComplete = skillCount > 0 || experienceCount > 0;
  const evidenceSaved = evidenceCounts.total > 0;
  const evidenceEligible = eligibleEvidenceCount > 0;

  const steps: ResumeBuilderReadinessStep[] = [
    {
      actionLabel: "Open Career Profile",
      complete: profileComplete,
      description:
        "Add at least one skill or employment record so evidence can link to real career facts.",
      href: "/career-profile",
      id: "profile",
      title: "Build your career profile",
    },
    {
      actionLabel: "Open Evidence Vault",
      complete: evidenceSaved,
      description:
        "Save evidence that supports your skills and roles. Resume Builder never invents missing facts.",
      href: "/evidence",
      id: "evidence",
      title: "Add evidence in Evidence Vault",
    },
    {
      actionLabel: "Review evidence",
      complete: evidenceEligible,
      description:
        evidenceCounts.confirmed > 0 && !evidenceEligible
          ? "Some evidence is saved but not yet eligible. Open each item and confirm it, resolving any conflicts or attachment issues."
          : "Open each evidence item and confirm it so it becomes eligible for resume generation.",
      href: "/evidence",
      id: "confirm",
      title: "Confirm evidence for resume use",
    },
  ];

  if (input.sourceError) {
    return {
      confirmedEvidenceCount: evidenceCounts.confirmed,
      draftEvidenceCount: evidenceCounts.draft,
      experienceCount,
      skillCount,
      status: "error",
      steps,
      summary: input.sourceError,
    };
  }

  if (!input.sourceOptions) {
    return {
      confirmedEvidenceCount: evidenceCounts.confirmed,
      draftEvidenceCount: evidenceCounts.draft,
      experienceCount,
      skillCount,
      status: "loading",
      steps,
    };
  }

  if (evidenceEligible) {
    return {
      confirmedEvidenceCount: evidenceCounts.confirmed,
      draftEvidenceCount: evidenceCounts.draft,
      experienceCount,
      skillCount,
      sourceOptions: input.sourceOptions,
      status: "ready",
      steps,
      summary: `${eligibleEvidenceCount} eligible evidence ${eligibleEvidenceCount === 1 ? "source" : "sources"} ready for resume generation.`,
    };
  }

  const nextStep = steps.find((step) => !step.complete) ?? steps.at(-1);
  return {
    confirmedEvidenceCount: evidenceCounts.confirmed,
    draftEvidenceCount: evidenceCounts.draft,
    experienceCount,
    skillCount,
    sourceOptions: input.sourceOptions,
    status: "blocked",
    steps,
    summary: nextStep
      ? `Next step: ${nextStep.title.toLowerCase()}.`
      : "Confirm eligible evidence before creating a resume.",
  };
}

export function evidenceRecordsFromPayload(
  payload: ListPayload | null,
): EvidenceRecord[] {
  return asList(payload?.data)
    .map((item) => asRecord(item))
    .filter((record): record is Record<string, unknown> => record !== null)
    .map((record) => ({
      state: typeof record.state === "string" ? record.state : undefined,
    }));
}
