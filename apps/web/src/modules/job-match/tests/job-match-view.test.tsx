import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Job, JobMatchAnalysis, OpportunityPriority } from "../api/types";
import { JobMatchView } from "../views/job-match-view";

const api = vi.hoisted(() => ({
  analyzeJob: vi.fn(),
  createJob: vi.fn(),
  deleteJob: vi.fn(),
  getJobs: vi.fn(),
  importJob: vi.fn(),
  prioritizeOpportunity: vi.fn(),
}));

vi.mock("../api/job-match-api", () => api);

const disclaimer =
  "CareerOS scores are internal readiness measurements. They are not scores provided by an employer or applicant tracking system and do not guarantee interviews or employment outcomes.";

const job: Job = {
  applicationDeadline: null,
  company: "Example Co",
  compensation: null,
  createdAt: "2026-07-19T12:00:00Z",
  employmentType: "full_time",
  id: "00000000-0000-4000-8000-000000000601",
  location: "Remote",
  requirements: [
    {
      confidenceBasisPoints: 9000,
      id: "00000000-0000-4000-8000-000000000701",
      importance: "mandatory",
      normalizedText: "must have experience with user research",
      order: 10,
      requirementType: "experience",
      sourceEnd: 104,
      sourceStart: 40,
      text: "Must have experience with user research.",
    },
  ],
  sourceKind: "paste",
  sourceUrl: null,
  targetRoleId: null,
  targetRoleTitle: null,
  title: "Product Manager",
  updatedAt: "2026-07-19T12:00:00Z",
  version: 1,
  workModel: "remote",
};

const analysis: JobMatchAnalysis = {
  components: [
    {
      contributionBasisPoints: 2000,
      dimension: "requirement_coverage",
      explanation: "Weighted coverage across applicable job requirements.",
      scoreBasisPoints: 8000,
      weightBasisPoints: 2500,
    },
  ],
  configurationVersion: "job-match-default/1",
  createdAt: "2026-07-19T12:00:00Z",
  displayScore: 82,
  engineVersion: "job-match/1.0.0",
  featureSchemaVersion: "job-match-features/1",
  hardGapCount: 0,
  id: "00000000-0000-4000-8000-000000000801",
  insufficientReason: null,
  job,
  rawScoreBasisPoints: 8200,
  readinessLabel: "strong",
  requirements: [
    {
      evidence: [
        {
          evidenceId: "00000000-0000-4000-8000-000000000901",
          evidenceStrength: "confirmed",
          evidenceTitle: "Confirmed discovery program",
          id: "00000000-0000-4000-8000-000000000902",
          rationale: "Eligible evidence overlaps this exact job requirement.",
          relevanceBasisPoints: 9000,
        },
      ],
      explanation: "Eligible evidence directly supports this requirement.",
      hardGap: false,
      id: "00000000-0000-4000-8000-000000000903",
      importance: "mandatory",
      matchState: "strong",
      recommendedAction: "Use the linked evidence when tailoring.",
      requirementId: job.requirements[0]!.id,
      requirementText: "Must have experience with user research.",
      requirementType: "experience",
      scoreBasisPoints: 10000,
    },
  ],
  scoringDisclaimer: disclaimer,
  summary:
    "Product Manager match is based on 1 strong requirement match and 0 gaps.",
};

const priority: OpportunityPriority = {
  analysisId: analysis.id,
  blockers: [],
  createdAt: "2026-07-19T12:00:00Z",
  id: "00000000-0000-4000-8000-000000001001",
  jobId: job.id,
  nextAction: "Prepare a tailored resume and application materials.",
  priorityLabel: "high",
  priorityScoreBasisPoints: 8400,
  reasonsFor: ["Application Readiness is 82/100.", "Interest is 5/5."],
  reconsiderations: [],
  scoringDisclaimer: disclaimer,
};

describe("Job Match view", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getJobs.mockResolvedValue({
      data: [],
      page: { hasMore: false, limit: 50, nextCursor: null },
    });
    api.createJob.mockResolvedValue(job);
    api.analyzeJob.mockResolvedValue(analysis);
    api.prioritizeOpportunity.mockResolvedValue(priority);
  });

  it("renders empty job and analysis states without demo data", async () => {
    render(<JobMatchView />);

    expect(
      await screen.findByRole("heading", { name: "Save a job posting" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "No saved jobs" }),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "Choose a job" })).toBeVisible();
    expect(screen.queryByText(/ATS score/i)).not.toBeInTheDocument();
  });

  it("saves, analyzes, and prioritizes a pasted job posting", async () => {
    render(<JobMatchView />);

    fireEvent.change(await screen.findByLabelText("Job title"), {
      target: { value: "Product Manager" },
    });
    fireEvent.change(screen.getByLabelText("Company"), {
      target: { value: "Example Co" },
    });
    fireEvent.change(screen.getByLabelText("Job description"), {
      target: {
        value:
          "Title: Product Manager\nRequirements:\n- Must have experience with user research.",
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save job" }));

    expect(
      await screen.findAllByText("Product Manager saved for matching."),
    ).not.toHaveLength(0);
    expect(api.createJob).toHaveBeenCalledWith(
      expect.objectContaining({
        sourceKind: "paste",
        sourceText: expect.stringContaining("user research"),
        title: "Product Manager",
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: "Analyze match" }));
    expect(
      await screen.findByLabelText("Application readiness: 82 out of 100"),
    ).toBeVisible();
    expect(screen.getByText("Confirmed discovery program")).toBeVisible();
    expect(screen.getByText(disclaimer)).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Calculate priority" }));
    expect(
      await screen.findByText(
        "Prepare a tailored resume and application materials.",
      ),
    ).toBeVisible();
    expect(api.prioritizeOpportunity).toHaveBeenCalledWith(
      job.id,
      expect.objectContaining({ analysisId: analysis.id, userInterest: 4 }),
    );
  });

  it("renders a retryable failure state", async () => {
    api.getJobs.mockRejectedValue(new Error("offline"));
    render(<JobMatchView />);

    expect(
      await screen.findByRole("heading", { name: "Job Match unavailable" }),
    ).toBeVisible();
  });
});
