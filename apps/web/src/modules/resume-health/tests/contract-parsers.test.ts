import { describe, expect, it } from "vitest";

import { parseReport } from "../api/contract-parsers";

const featureValue = {
  key: "image_only",
  label: "Image-only document",
  kind: "boolean",
  rawValue: false,
  displayValue: "No",
};

const featureContribution = {
  key: "searchable_text",
  label: "Searchable text",
  score: 61,
  rawScoreBasisPoints: 6120,
  weight: 30,
  rawWeightBasisPoints: 3000,
  contribution: 18,
  rawContributionBasisPoints: 1836,
};

const report = {
  id: "00000000-0000-4000-8000-000000000030",
  documentId: "00000000-0000-4000-8000-000000000010",
  canonicalResumeId: "00000000-0000-4000-8000-000000000020",
  status: "complete",
  score: 73,
  rawScoreBasisPoints: 7300,
  scoreBand: "developing",
  scoreType: "resume_health",
  engineVersion: "resume-health/1.0.0",
  configurationVersion: "resume-health-default/1",
  featureSchemaVersion: "resume-health-features/1",
  featureSetHash: "sha256:fictional",
  featureValues: [featureValue],
  components: [
    {
      key: "machine_readability",
      label: "Machine Readability",
      score: 80,
      rawScoreBasisPoints: 8000,
      weight: 25,
      contribution: 20,
      rawContributionBasisPoints: 2000,
      explanation: "Searchable text and reading order were measured.",
      featureContributions: [featureContribution],
    },
  ],
  findings: [],
  warnings: [],
  disclaimer: "Internal measure only.",
  computedAt: "2026-07-15T00:00:00Z",
  expiresAt: null,
};

describe("Resume Health report contract parser", () => {
  it("accepts a bounded feature trace without coercing boolean observations", () => {
    const parsed = parseReport(report);

    expect(parsed.featureValues[0]?.rawValue).toBe(false);
    expect(
      parsed.components[0]?.featureContributions[0]?.rawContributionBasisPoints,
    ).toBe(1836);
  });

  it("rejects malformed feature values and out-of-range contributions", () => {
    expect(() =>
      parseReport({
        ...report,
        featureValues: [{ ...featureValue, rawValue: 0 }],
      }),
    ).toThrow("Invalid Resume Health feature value response.");

    expect(() =>
      parseReport({
        ...report,
        components: [
          {
            ...report.components[0],
            featureContributions: [
              { ...featureContribution, rawContributionBasisPoints: 10_001 },
            ],
          },
        ],
      }),
    ).toThrow("Invalid Resume Health feature contribution response.");
  });
});
