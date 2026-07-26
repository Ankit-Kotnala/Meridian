import { describe, expect, it } from "vitest";

import {
  parseEvidence,
  parseProfileImportBatch,
  parseProfileImportProposal,
} from "../api/contract-parsers";

const evidence = {
  archivedAt: null,
  attachments: [],
  conflicts: [],
  createdAt: "2026-07-15T00:00:00Z",
  description: "A user-entered statement with no inferred facts.",
  eligibilityReasons: ["owner_confirmation_required"],
  endDate: null,
  factualEligible: false,
  history: [],
  id: "00000000-0000-4000-8000-000000000301",
  lifecycle: "active",
  metrics: [],
  numericEligible: false,
  organizationOrProject: null,
  provenance: [
    {
      available: true,
      confidence: null,
      id: "00000000-0000-4000-8000-000000000302",
      parserVersion: null,
      sourceDocumentId: null,
      sourceLabel: "Manual entry",
      sourceRevision: null,
      sourceSnapshotId: null,
      sourceType: "manual",
      spans: [],
      userConfirmed: false,
    },
  ],
  revision: 1,
  startDate: null,
  state: "inferred",
  title: "Customer onboarding note",
  type: "user_note",
  updatedAt: "2026-07-15T00:00:00Z",
  usage: [],
  userConfirmed: false,
  version: 1,
};

describe("Career Vault evidence contract parser", () => {
  it("preserves authoritative false eligibility and source availability", () => {
    const parsed = parseEvidence(evidence);

    expect(parsed.factualEligible).toBe(false);
    expect(parsed.numericEligible).toBe(false);
    expect(parsed.provenance[0]?.available).toBe(true);
    expect(parsed.eligibilityReasons).toEqual(["owner_confirmation_required"]);
  });

  it("rejects evidence when either authoritative eligibility boolean is absent", () => {
    const withoutFactual: Partial<typeof evidence> = { ...evidence };
    const withoutNumeric: Partial<typeof evidence> = { ...evidence };
    delete withoutFactual.factualEligible;
    delete withoutNumeric.numericEligible;

    expect(() => parseEvidence(withoutFactual)).toThrow(
      "Invalid factual generation eligibility response.",
    );
    expect(() => parseEvidence(withoutNumeric)).toThrow(
      "Invalid numeric generation eligibility response.",
    );
  });

  it("rejects malformed evidence states instead of coercing them", () => {
    expect(() => parseEvidence({ ...evidence, state: "approved" })).toThrow(
      "Invalid evidence state response.",
    );
  });

  it("preserves year-only source precision and rejects invented day precision", () => {
    const parsed = parseEvidence({
      ...evidence,
      endDate: "2025",
      startDate: "2024",
    });

    expect(parsed.startDate).toBe("2024");
    expect(parsed.endDate).toBe("2025");
    expect(() =>
      parseEvidence({ ...evidence, startDate: "2024-01-01" }),
    ).toThrow("Invalid evidence start date response.");
  });
});

const semanticProposal = {
  conflictCode: null,
  createdAt: "2026-07-26T00:00:00Z",
  documentId: "00000000-0000-4000-8000-000000000501",
  fields: [
    {
      acceptedValue: null,
      anchors: [
        {
          blockId: "00000000-0000-4000-8000-000000000502",
          digest: `sha256:${"ab".repeat(32)}`,
          end: 117,
          excerpt: "Software Engineer",
          page: 1,
          start: 100,
        },
      ],
      confidence: 90,
      datePrecision: null,
      fieldType: "text",
      id: "00000000-0000-4000-8000-000000000503",
      name: "title",
      proposedValue: "Software Engineer",
      reviewState: "corrected",
    },
  ],
  id: "00000000-0000-4000-8000-000000000504",
  parserVersion: "local-semantic/1",
  schemaVersion: "canonical-semantics/1.0.0",
  semanticEntityId: "00000000-0000-4000-8000-000000000505",
  semanticKind: "experience",
  snapshotId: "00000000-0000-4000-8000-000000000506",
  snapshotRevision: 2,
  sourceAvailable: true,
  status: "pending",
  target: "entity",
  targetRecordId: null,
  updatedAt: "2026-07-26T00:00:00Z",
  version: 1,
};

describe("Career Vault typed import contract parser", () => {
  it("preserves semantic field identity and exact source excerpts", () => {
    const parsed = parseProfileImportProposal(semanticProposal);

    expect(parsed.changes[0]).toMatchObject({
      field: "title",
      id: semanticProposal.fields[0]!.id,
      proposedValue: "Software Engineer",
      source: {
        available: true,
        sourceType: "resume_semantic",
        spans: [
          {
            end: 117,
            excerpt: "Software Engineer",
            start: 100,
          },
        ],
      },
    });
  });

  it("keeps incomplete semantic candidates as questions rather than facts", () => {
    const parsed = parseProfileImportBatch({
      proposals: [],
      questions: [
        {
          code: "semantic_candidate_requires_review",
          missingFields: ["employer"],
          semanticEntityId: semanticProposal.semanticEntityId,
        },
      ],
    });

    expect(parsed.proposals).toEqual([]);
    expect(parsed.questions[0]?.missingFields).toEqual(["employer"]);
  });
});
