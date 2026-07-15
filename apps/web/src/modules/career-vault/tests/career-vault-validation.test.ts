import { describe, expect, it } from "vitest";

import type { AchievementInput, EvidenceInput } from "../api/types";
import {
  validateAchievementConversion,
  validateCareerItem,
  validateEvidence,
  validateExperience,
} from "../validation/career-vault-validation";

describe("Career Vault validation", () => {
  it("keeps experience dates at year-month precision and rejects inverted ranges", () => {
    expect(
      validateExperience({
        current: false,
        description: "",
        displayTitle: null,
        employer: "Fictional Co",
        employmentType: "full_time",
        endDate: "2024-03",
        groupWithExperienceId: null,
        location: null,
        officialTitle: "Engineer",
        skillIds: [],
        startDate: "2024-04",
      }).endDate,
    ).toBe("End month cannot be before the start month.");

    expect(
      validateExperience({
        current: true,
        description: "",
        displayTitle: null,
        employer: "Fictional Co",
        employmentType: null,
        endDate: null,
        groupWithExperienceId: null,
        location: null,
        officialTitle: "Engineer",
        skillIds: [],
        startDate: "2024-04-01",
      }).startDate,
    ).toBe("Choose a start month and year.");
  });

  it("requires complete, bounded structured metric fields", () => {
    const input: EvidenceInput = {
      attachmentIds: [],
      description: "A measured result supplied by the user.",
      endDate: null,
      experienceIds: [],
      metrics: [
        {
          attribution: "team",
          baseline: null,
          comparator: null,
          name: "Cycle time",
          periodEnd: null,
          periodStart: "2025-01",
          precision: "exact",
          unit: "days",
          value: "12.12345",
        },
      ],
      organizationOrProject: null,
      skillIds: [],
      source: {
        blockId: null,
        documentId: null,
        end: null,
        page: null,
        snapshotId: null,
        sourceType: "manual",
        start: null,
        url: null,
      },
      startDate: null,
      title: "Cycle-time observation",
      type: "metric",
    };

    expect(validateEvidence(input).metric0Value).toContain(
      "four decimal places",
    );
  });

  it("requires HTTP(S) for portfolio links", () => {
    expect(
      validateCareerItem({
        description: "",
        endDate: null,
        kind: "portfolio_link",
        organization: null,
        startDate: null,
        title: "Portfolio",
        url: "javascript:alert(1)",
      }).url,
    ).toBe("Enter a valid HTTP(S) URL.");
  });

  it("does not convert an achievement until required answers are explicit", () => {
    const input: AchievementInput = {
      answers: {
        affected: "",
        changed: "",
        collaboration: "",
        delivered: "A release",
        measurement: "",
        methods: "",
        problem: "A deployment issue",
      },
      employerId: null,
      metric: null,
      projectId: null,
      title: "Release work",
    };

    expect(validateAchievementConversion(input).changed).toContain(
      "what changed",
    );
  });
});
