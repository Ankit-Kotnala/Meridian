import { describe, expect, it } from "vitest";

import type { ProfileImportChange, ProfileImportProposal } from "../api/types";
import {
  AUTO_IMPORT_MIN_CONFIDENCE,
  autoImportHold,
  isAutoApplicable,
  planAutoImport,
} from "../auto-import/eligibility";

function change(
  overrides: Partial<ProfileImportChange> & {
    confidence?: number | null;
    spans?: number;
  } = {},
): ProfileImportChange {
  const { confidence = 0.98, spans = 1, ...rest } = overrides;
  return {
    conflict: null,
    currentValue: null,
    field: "employer",
    id: "field-1",
    label: "Employer",
    proposedValue: "Fictional Systems",
    reviewState: "confirmed",
    source: {
      available: true,
      confidence,
      id: "proposal-1:field-1",
      parserVersion: "1.0.0",
      sourceDocumentId: "00000000-0000-4000-8000-000000000001",
      sourceLabel: "Confirmed typed resume field",
      sourceRevision: 1,
      sourceSnapshotId: "00000000-0000-4000-8000-000000000002",
      sourceType: "resume_semantic",
      spans: Array.from({ length: spans }, (_, index) => ({
        digest: `digest-${index}`,
        end: 10,
        excerpt: "Fictional Systems",
        id: `block-1:${index}`,
        page: 1,
        start: 0,
      })),
      userConfirmed: false,
    },
    ...rest,
  } as ProfileImportChange;
}

function proposal(
  overrides: Partial<ProfileImportProposal> = {},
): ProfileImportProposal {
  return {
    changes: [change()],
    createdAt: "2026-08-17T00:00:00Z",
    id: "proposal-1",
    sourceAvailable: true,
    sourceDocumentName: "reviewed resume snapshot 1",
    status: "pending",
    version: 1,
    ...overrides,
  };
}

describe("auto import eligibility", () => {
  it("applies a confirmed, anchored, confident proposal without asking again", () => {
    expect(autoImportHold(proposal())).toBeNull();
    expect(isAutoApplicable(proposal())).toBe(true);
  });

  it("applies a value the user typed during review even without an anchor", () => {
    const typed = proposal({
      changes: [
        change({ confidence: null, reviewState: "user_added", spans: 0 }),
      ],
    });

    expect(autoImportHold(typed)).toBeNull();
  });

  it("holds anything that conflicts with an existing record", () => {
    const conflicting = proposal({
      changes: [
        change(),
        change({ conflict: "employer_mismatch", id: "field-2" }),
      ],
    });

    expect(autoImportHold(conflicting)).toBe("conflict");
    expect(isAutoApplicable(conflicting)).toBe(false);
  });

  it("applies a confirmed value that cannot be traced back to the file", () => {
    expect(autoImportHold(proposal({ changes: [change({ spans: 0 })] }))).toBeNull();
  });

  it("applies a confirmed value below the confidence floor", () => {
    expect(
      autoImportHold(
        proposal({
          changes: [change({ confidence: AUTO_IMPORT_MIN_CONFIDENCE - 0.01 })],
        }),
      ),
    ).toBeNull();
  });

  it("applies a parsed value exactly at the confidence floor", () => {
    expect(
      autoImportHold(
        proposal({
          changes: [change({ confidence: AUTO_IMPORT_MIN_CONFIDENCE })],
        }),
      ),
    ).toBeNull();
  });

  it("treats unknown parser confidence on a reviewed field as acceptable", () => {
    expect(
      autoImportHold(proposal({ changes: [change({ confidence: null })] })),
    ).toBeNull();
  });

  it("holds a proposal whose reviewed snapshot is gone", () => {
    expect(autoImportHold(proposal({ sourceAvailable: false }))).toBe(
      "sourceUnavailable",
    );
  });

  it("holds a proposal that carries no fields", () => {
    expect(autoImportHold(proposal({ changes: [] }))).toBe("untraceable");
  });

  it("never reports a hold for a proposal that is already decided", () => {
    expect(
      autoImportHold(proposal({ sourceAvailable: false, status: "accepted" })),
    ).toBeNull();
    expect(isAutoApplicable(proposal({ status: "accepted" }))).toBe(false);
    expect(isAutoApplicable(proposal({ status: "rejected" }))).toBe(false);
  });
});

describe("auto import planning", () => {
  it("splits pending proposals and ignores decided ones", () => {
    const plan = planAutoImport([
      proposal({ id: "clean-1" }),
      proposal({ id: "clean-2" }),
      proposal({
        changes: [change({ conflict: "duplicate_employer" })],
        id: "conflicted",
      }),
      proposal({ id: "already-done", status: "accepted" }),
    ]);

    expect(plan.apply.map(({ id }) => id)).toEqual(["clean-1", "clean-2"]);
    expect(plan.hold).toHaveLength(1);
    expect(plan.hold[0]).toMatchObject({
      hold: "conflict",
      proposal: { id: "conflicted" },
    });
  });

  it("returns an empty plan for an empty inbox", () => {
    expect(planAutoImport([])).toEqual({ apply: [], hold: [] });
  });
});
