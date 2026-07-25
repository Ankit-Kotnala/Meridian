import { describe, expect, it } from "vitest";

import { parseCanonical, parseReport } from "../api/contract-parsers";

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

  it("accepts the seven-contribution Resume Health v2 consistency trace", () => {
    const keys = [
      "parser_confidence",
      "parser_warning_integrity",
      "duplicate_content_integrity",
      "chronology_coverage",
      "source_anchor_coverage",
      "semantic_review_coverage",
      "date_precision_coverage",
    ];

    const parsed = parseReport({
      ...report,
      components: [
        {
          ...report.components[0],
          key: "consistency_truth",
          featureContributions: keys.map((key) => ({
            ...featureContribution,
            key,
          })),
        },
      ],
    });

    expect(parsed.components[0]?.featureContributions).toHaveLength(7);
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

    expect(() =>
      parseReport({
        ...report,
        components: [
          {
            ...report.components[0],
            featureContributions: [
              "searchable_text",
              "parser_confidence",
              "reading_order_integrity",
              "recognized_section_ratio",
              "source_anchor_coverage",
              "semantic_review_coverage",
              "date_precision_coverage",
              "semantic_breadth",
            ].map((key) => ({ ...featureContribution, key })),
          },
        ],
      }),
    ).toThrow("Invalid Resume Health component response.");
  });
});

describe("canonical semantic contract parser", () => {
  const canonical = {
    id: "00000000-0000-4000-8000-000000000001",
    documentId: "00000000-0000-4000-8000-000000000002",
    schemaVersion: "canonical-resume/2.0.0",
    version: 1,
    sections: [],
    warnings: [],
    semanticSchemaVersion: "canonical-semantics/1.0.0",
    semanticParserVersion: "careeros-semantic-parser/1.0.0",
    semanticReviewState: "unreviewed",
    semanticEntities: [
      {
        id: "00000000-0000-4000-8000-000000000003",
        kind: "experience",
        reviewState: "unreviewed",
        sourceSectionId: "00000000-0000-4000-8000-000000000004",
        fields: [
          {
            id: "00000000-0000-4000-8000-000000000005",
            name: "title",
            fieldType: "text",
            value: "Engineer",
            confidence: 80,
            reviewState: "unreviewed",
            datePrecision: null,
            anchors: [
              {
                blockId: "00000000-0000-4000-8000-000000000006",
                page: 1,
                start: 0,
                end: 8,
                sourceSha256: "a".repeat(64),
                excerpt: "Engineer",
              },
            ],
          },
        ],
      },
    ],
    semanticWarnings: [],
    legacyUpgradeRequired: false,
    correctedByUser: false,
    createdAt: "2026-07-25T00:00:00Z",
  };

  it("accepts a bounded source-anchored semantic graph", () => {
    expect(parseCanonical(canonical).semanticEntities).toHaveLength(1);
  });

  it("rejects ungrounded parser fields and inconsistent legacy metadata", () => {
    expect(() =>
      parseCanonical({
        ...canonical,
        semanticEntities: [
          {
            ...canonical.semanticEntities[0],
            fields: [
              {
                ...canonical.semanticEntities[0]!.fields[0],
                anchors: [],
              },
            ],
          },
        ],
      }),
    ).toThrow("Invalid semantic field response.");
    expect(() =>
      parseCanonical({
        ...canonical,
        legacyUpgradeRequired: true,
      }),
    ).toThrow("Invalid canonical resume response.");
  });
});
