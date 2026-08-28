import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  Job,
  JobCatalogBrowse,
  JobCatalogSearch,
  JobMatchAnalysis,
  OpportunityPriority,
  RolePreference,
} from "../api/types";
import { JobMatchView } from "../views/job-match-view";

const api = vi.hoisted(() => ({
  analyzeJob: vi.fn(),
  browseJobCatalog: vi.fn(),
  createApplicationForJob: vi.fn(),
  deleteJob: vi.fn(),
  generateAssistedApplyPack: vi.fn(),
  getJobCatalogSuggestions: vi.fn(),
  getJobs: vi.fn(),
  listResumesForApply: vi.fn(),
  prioritizeOpportunity: vi.fn(),
  saveJobCatalogListing: vi.fn(),
  setJobCatalogRolePreferences: vi.fn(),
}));

vi.mock("../api/job-match-api", () => api);

const disclaimer =
  "Meridian scores are internal readiness measurements. They are not scores provided by an employer or applicant tracking system and do not guarantee interviews or employment outcomes.";

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

const catalogListing: JobCatalogSearch["listings"][number] = {
  applicationUrl: "https://remotive.com/remote-jobs/all-others/example-1",
  company: "Fixture Co",
  externalId: "fake-1",
  location: "Remote",
  platform: "remotive",
  postedAt: null,
  remote: true,
  sourceText: "Build backend services.",
  title: "Backend Engineer",
};

const emptyRolePreference: RolePreference = { roleTitles: [] };

describe("Job Match view", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getJobs.mockResolvedValue({
      data: [],
      page: { hasMore: false, limit: 50, nextCursor: null },
    });
    api.analyzeJob.mockResolvedValue(analysis);
    api.prioritizeOpportunity.mockResolvedValue(priority);
    api.getJobCatalogSuggestions.mockResolvedValue({
      listings: [],
      matchedTargetRole: false,
      selectedRoleTitles: [],
      suggestedRoleTitles: [],
      targetRoleTitles: [],
    } satisfies JobCatalogSearch);
    api.setJobCatalogRolePreferences.mockResolvedValue(emptyRolePreference);
    api.browseJobCatalog.mockResolvedValue({
      hasMore: false,
      listings: [],
      nextOffset: 0,
    } satisfies JobCatalogBrowse);
  });

  it("renders empty job states without demo data and without manual job entry", async () => {
    render(<JobMatchView />);

    expect(
      await screen.findByRole("heading", { name: "No saved jobs" }),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "Choose a job" })).toBeVisible();
    expect(screen.queryByText(/ATS score/i)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Save a job posting" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Import from URL"),
    ).not.toBeInTheDocument();
  });

  it("shows catalog suggestions, saves one, and analyzes/prioritizes it", async () => {
    api.getJobCatalogSuggestions.mockResolvedValue({
      listings: [catalogListing],
      matchedTargetRole: true,
      selectedRoleTitles: [],
      suggestedRoleTitles: ["Backend Engineer"],
      targetRoleTitles: ["Backend Engineer"],
    } satisfies JobCatalogSearch);
    const savedJob: Job = { ...job, title: "Backend Engineer" };
    api.saveJobCatalogListing.mockResolvedValue(savedJob);
    api.analyzeJob.mockResolvedValue({
      ...analysis,
      job: savedJob,
      summary:
        "Backend Engineer match is based on 1 strong requirement match and 0 gaps.",
    });

    render(<JobMatchView />);

    expect(
      await screen.findByRole("heading", { name: "Suggested for you" }),
    ).toBeVisible();
    // "Backend Engineer" also appears as a role-filter chip, so assert
    // there's at least one match rather than a single unique node.
    expect(screen.getAllByText("Backend Engineer").length).toBeGreaterThan(0);
    expect(
      screen.getByText("Matched toward Backend Engineer from published job boards."),
    ).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Save to my jobs" }));

    expect(
      await screen.findAllByText("Backend Engineer saved for matching."),
    ).not.toHaveLength(0);
    expect(api.saveJobCatalogListing).toHaveBeenCalledWith("remotive", "fake-1");

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
      savedJob.id,
      expect.objectContaining({ analysisId: analysis.id, userInterest: 4 }),
    );
  });

  it("lets an owner opt out of a suggested role, persisting the change", async () => {
    api.getJobCatalogSuggestions.mockResolvedValue({
      listings: [],
      matchedTargetRole: false,
      selectedRoleTitles: [],
      suggestedRoleTitles: ["Backend Engineer"],
      targetRoleTitles: ["Backend Engineer"],
    } satisfies JobCatalogSearch);
    api.setJobCatalogRolePreferences.mockResolvedValue({
      roleTitles: [],
    } satisfies RolePreference);

    render(<JobMatchView />);

    expect(await screen.findByText("Backend Engineer")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Remove Backend Engineer" }));

    await waitFor(() =>
      expect(api.setJobCatalogRolePreferences).toHaveBeenCalledWith([]),
    );
    // Suggestions are reloaded after the preference change.
    await waitFor(() =>
      expect(api.getJobCatalogSuggestions).toHaveBeenCalledTimes(2),
    );
  });

  it("lets an owner add a custom role to the filter", async () => {
    render(<JobMatchView />);

    await screen.findByRole("heading", { name: "No saved jobs" });

    fireEvent.change(screen.getByLabelText("Add a role title"), {
      target: { value: "Staff Data Engineer" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));

    expect(api.setJobCatalogRolePreferences).toHaveBeenCalledWith([
      "Staff Data Engineer",
    ]);
  });

  it("searches the full job catalog independent of the role filter", async () => {
    api.browseJobCatalog.mockResolvedValue({
      hasMore: false,
      listings: [catalogListing],
      nextOffset: 1,
    } satisfies JobCatalogBrowse);
    api.saveJobCatalogListing.mockResolvedValue({
      ...job,
      title: "Backend Engineer",
    });

    render(<JobMatchView />);

    fireEvent.change(await screen.findByLabelText("Search all jobs by keyword"), {
      target: { value: "backend" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(await screen.findByText("Backend Engineer")).toBeVisible();
    expect(api.browseJobCatalog).toHaveBeenCalledWith(
      expect.objectContaining({ limit: 10, offset: 0, q: "backend" }),
    );

    fireEvent.click(screen.getByRole("button", { name: "Save to my jobs" }));
    expect(
      await screen.findAllByText("Backend Engineer saved for matching."),
    ).not.toHaveLength(0);
  });

  it("prepares an assisted-apply pack for a saved job", async () => {
    api.getJobs.mockResolvedValue({
      data: [job],
      page: { hasMore: false, limit: 50, nextCursor: null },
    });
    api.listResumesForApply.mockResolvedValue([
      {
        createdAt: "2026-07-01T12:00:00Z",
        currentVersion: 2,
        currentVersionId: "00000000-0000-4000-8000-000000001101",
        id: "00000000-0000-4000-8000-000000001100",
        layout: "standard",
        targetRole: null,
        template: "modern",
        title: "Product Manager Resume",
        updatedAt: "2026-07-20T12:00:00Z",
        version: 2,
      },
    ]);
    api.createApplicationForJob.mockResolvedValue({ id: "app-1" });
    api.generateAssistedApplyPack.mockResolvedValue(undefined);

    render(<JobMatchView />);

    fireEvent.click(await screen.findByRole("button", { name: "Apply for me" }));

    expect(
      await screen.findAllByText(/application pack ready using/i),
    ).not.toHaveLength(0);
    expect(api.createApplicationForJob).toHaveBeenCalledWith(
      job.id,
      "00000000-0000-4000-8000-000000001101",
    );
    expect(api.generateAssistedApplyPack).toHaveBeenCalledWith("app-1");
  });

  it("renders a retryable failure state", async () => {
    api.getJobs.mockRejectedValue(new Error("offline"));
    render(<JobMatchView />);

    expect(
      await screen.findByRole("heading", { name: "Job Match unavailable" }),
    ).toBeVisible();
  });
});
