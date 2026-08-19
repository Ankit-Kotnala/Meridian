import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  claimGuestDocument: vi.fn(),
  deleteDocument: vi.fn(),
  getDocument: vi.fn(),
  getResumeHealthReport: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn() }),
}));
vi.mock("@/modules/career-vault", () => ({
  AutoImportRunner: () => null,
}));
vi.mock("../api/resume-health-api", () => ({
  ...api,
  ApiRequestError: class extends Error {
    failure = { status: 500 };
  },
}));

import {
  ResumeHealthReportView,
  SCORE_DISCLAIMER,
} from "../views/resume-health-report-view";

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
  featureValues: [
    {
      key: "text_characters",
      label: "Extractable characters",
      kind: "count",
      rawValue: 612,
      displayValue: "612",
    },
    {
      key: "image_only",
      label: "Image-only document",
      kind: "boolean",
      rawValue: false,
      displayValue: "No",
    },
  ],
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
      featureContributions: [
        {
          key: "searchable_text",
          label: "Searchable text",
          score: 61,
          rawScoreBasisPoints: 6120,
          weight: 30,
          rawWeightBasisPoints: 3000,
          contribution: 18,
          rawContributionBasisPoints: 1836,
        },
      ],
    },
  ],
  findings: [
    {
      id: "improve-summary",
      severity: "warning",
      category: "issue",
      title: "Clarify summary",
      description: "The summary is longer than the configured clarity range.",
      section: "Recruiter Clarity",
      action: null,
    },
  ],
  warnings: [],
  disclaimer: SCORE_DISCLAIMER,
  computedAt: "2026-07-15T00:00:00Z",
  expiresAt: null,
} as const;

describe("Resume Health report", () => {
  it("renders real components, a text equivalent, and the canonical disclaimer", async () => {
    api.getResumeHealthReport.mockResolvedValue(report);
    api.getDocument.mockResolvedValue({
      id: report.documentId,
      displayFilename: "fictional.pdf",
      mediaType: "application/pdf",
      sizeBytes: 500,
      status: "reviewReady",
      version: 2,
      currentCanonicalResumeId: report.canonicalResumeId,
      latestAnalysisId: report.id,
      createdAt: "2026-07-15T00:00:00Z",
      updatedAt: "2026-07-15T00:00:00Z",
      expiresAt: null,
      canonicalResume: null,
    });
    render(<ResumeHealthReportView access="account" analysisId={report.id} />);

    expect(
      await screen.findByRole("img", { name: "Resume Health Score: 73/100" }),
    ).toBeVisible();
    expect(screen.getAllByText(SCORE_DISCLAIMER).length).toBeGreaterThan(0);
    expect(
      screen.getByRole("progressbar", {
        name: "Machine Readability (25% weight): 80 out of 100",
      }),
    ).toBeVisible();
    const contributionSummary = screen.getByText(
      "How Machine Readability was calculated",
    );
    const contributionDetails = contributionSummary.closest("details");
    expect(contributionDetails).not.toHaveAttribute("open");
    fireEvent.click(contributionSummary);
    expect(contributionDetails).toHaveAttribute("open");
    expect(
      screen.getByText(/61\.2% times 30% = 18\.36 component points/i),
    ).toBeVisible();

    fireEvent.click(screen.getByRole("tab", { name: "Methodology" }));
    expect(screen.getByText("resume-health-features/1")).toBeVisible();
    const inputSummary = screen.getByText("View measured input values");
    fireEvent.click(inputSummary);
    expect(inputSummary.closest("details")).toHaveAttribute("open");
    expect(screen.getByText("Extractable characters")).toBeVisible();
    expect(screen.getByText("612")).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "resume import review" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/Career Record import not ready/i),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Review parsed resume" }),
    ).toHaveAttribute(
      "href",
      `/resume-health/account/review/${report.documentId}`,
    );

    fireEvent.click(screen.getByRole("tab", { name: "All findings" }));
    expect(screen.getByText("Clarify summary")).toBeVisible();
    expect(screen.queryByText(/hiring probability/i)).not.toBeInTheDocument();
  });

  it("offers import review once parsed fields are reviewed", async () => {
    const reviewedSnapshotId = "00000000-0000-4000-8000-000000000021";
    api.getResumeHealthReport.mockResolvedValue(report);
    api.getDocument.mockResolvedValue({
      id: report.documentId,
      displayFilename: "fictional.pdf",
      mediaType: "application/pdf",
      sizeBytes: 500,
      status: "ready",
      version: 3,
      currentCanonicalResumeId: reviewedSnapshotId,
      latestAnalysisId: report.id,
      createdAt: "2026-07-15T00:00:00Z",
      updatedAt: "2026-07-15T00:00:00Z",
      expiresAt: null,
      canonicalResume: {
        id: reviewedSnapshotId,
        revision: 3,
        semanticReviewState: "confirmed",
      },
    });
    render(<ResumeHealthReportView access="account" analysisId={report.id} />);

    expect(
      await screen.findByRole("link", { name: "resume import review" }),
    ).toHaveAttribute(
      "href",
      `/career-profile/imports?documentId=${report.documentId}&snapshotId=${reviewedSnapshotId}`,
    );
  });

  it("does not turn insufficient data into a zero score", async () => {
    api.getResumeHealthReport.mockResolvedValueOnce({
      ...report,
      status: "insufficientData",
      score: null,
      rawScoreBasisPoints: null,
      scoreBand: null,
      components: [],
    });
    render(<ResumeHealthReportView access="account" analysisId={report.id} />);
    expect(await screen.findByText("Score unavailable")).toBeVisible();
    expect(screen.getByText("Not enough reliable data")).toBeVisible();
    expect(
      screen.queryByRole("img", { name: /Resume Health Score/ }),
    ).not.toBeInTheDocument();
  });
});
