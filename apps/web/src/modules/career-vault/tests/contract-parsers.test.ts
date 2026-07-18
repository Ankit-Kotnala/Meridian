import { describe, expect, it } from "vitest";

import { parseEvidence } from "../api/contract-parsers";

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
