import { describe, expect, it } from "vitest";

import { buildReadinessSnapshot } from "../lib/readiness";

describe("resume builder readiness", () => {
  it("marks the source ready when eligible evidence exists", () => {
    const snapshot = buildReadinessSnapshot({
      evidencePayload: {
        data: [{ state: "confirmed" }, { state: "supported" }],
      },
      experiencesPayload: { data: [{ id: "role-1" }] },
      skillsPayload: { data: [{ id: "skill-1" }] },
      sourceOptions: {
        bullets: [
          {
            evidenceIds: ["evidence-1"],
            evidenceReferences: [],
            sectionKind: "experience",
            source: "career_record",
            text: "Shipped discovery work",
          },
        ],
        headline: "Product lead",
        skills: ["Product discovery"],
        sourceEvidenceIds: ["evidence-1"],
        summary: null,
      },
    });

    expect(snapshot.status).toBe("ready");
    expect(snapshot.steps.every((step) => step.complete)).toBe(true);
  });

  it("points users to evidence confirmation when only draft evidence exists", () => {
    const snapshot = buildReadinessSnapshot({
      evidencePayload: {
        data: [{ state: "supported" }],
      },
      experiencesPayload: { data: [{ id: "role-1" }] },
      skillsPayload: { data: [{ id: "skill-1" }] },
      sourceOptions: {
        bullets: [],
        headline: null,
        skills: [],
        sourceEvidenceIds: [],
        summary: null,
      },
    });

    expect(snapshot.status).toBe("blocked");
    expect(snapshot.steps.find((step) => step.id === "confirm")?.complete).toBe(
      false,
    );
    expect(snapshot.summary).toMatch(/confirm evidence/i);
  });
});
