import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ApplicationSummary, DefenseMap, StarStory } from "../api/types";
import { InterviewPrepView } from "../views/interview-prep-view";

const api = vi.hoisted(() => ({
  createSession: vi.fn(),
  createStory: vi.fn(),
  getDefenseMap: vi.fn(),
  listInterviewApplications: vi.fn(),
  listSessions: vi.fn(),
  listStories: vi.fn(),
}));

vi.mock("../api/interview-prep-api", () => api);

const application: ApplicationSummary = {
  applicationDeadline: null,
  company: "Example Co",
  createdAt: "2026-07-24T09:00:00Z",
  eventCount: 0,
  followUpAt: null,
  id: "00000000-0000-4000-8000-000000000101",
  industry: "Technology",
  jobAnalysisId: null,
  jobId: "00000000-0000-4000-8000-000000000102",
  jobTitle: "Principal Engineer",
  jobVersion: 2,
  location: "Remote",
  noteCount: 0,
  offerSummary: null,
  openTaskCount: 0,
  outcomeStatus: "none",
  packCount: 0,
  referralStatus: "none",
  rejectionReason: null,
  resumeId: "00000000-0000-4000-8000-000000000103",
  resumeTitle: "Principal Engineer resume",
  resumeVersionId: "00000000-0000-4000-8000-000000000104",
  resumeVersionNumber: 4,
  source: "Company site",
  stage: "interview",
  taskCount: 0,
  updatedAt: "2026-07-24T09:00:00Z",
  version: 1,
};

const defenseMap: DefenseMap = {
  applicationId: application.id,
  defendedCount: 0,
  entries: [
    {
      claimId: "00000000-0000-4000-8000-000000000105",
      claimText: "Reduced build time by 40 percent.",
      evidenceRevisionIds: ["00000000-0000-4000-8000-000000000106"],
      status: "undefended",
      storyIds: [],
      strong: true,
      warning: "Strong claim lacks a ready defensible story.",
    },
  ],
  partialCount: 0,
  strongClaimWarningCount: 1,
  undefendedCount: 1,
};

const story: StarStory = {
  action: "I profiled the build and parallelized independent targets.",
  applicationId: application.id,
  claimPins: [
    {
      claimSha256: "a".repeat(64),
      claimText: defenseMap.entries[0]!.claimText,
      evidencePins: [
        {
          evidenceId: "00000000-0000-4000-8000-000000000107",
          evidenceRevisionId: defenseMap.entries[0]!.evidenceRevisionIds[0]!,
          hasNumericClaim: true,
          revisionNumber: 3,
          statement: "Measured build duration fell from 10 to 6 minutes.",
          statementSha256: "b".repeat(64),
          strength: "confirmed",
        },
      ],
      fieldNames: ["situation", "task", "action", "result"],
      sourceClaimId: defenseMap.entries[0]!.claimId,
      strong: true,
    },
  ],
  confidence: 4,
  createdAt: "2026-07-24T10:00:00Z",
  followUpQuestions: ["How was the reduction measured?"],
  groundingStatus: "current",
  groundingWarning: null,
  id: "00000000-0000-4000-8000-000000000108",
  metricExplanation: "CI duration fell from 10 to 6 minutes.",
  origin: "user_authored",
  personalContribution: "I designed and implemented the build graph changes.",
  result: "The measured build duration fell by 40 percent.",
  situation: "Build feedback took ten minutes.",
  status: "ready",
  task: "Reduce feedback time without weakening tests.",
  title: "Faster build feedback",
  updatedAt: "2026-07-24T10:00:00Z",
  version: 1,
};

describe("Interview Prep view", () => {
  function renderView() {
    return render(
      <InterviewPrepView
        roadmapPanel={<div data-testid="roadmap-panel">Role roadmap</div>}
      />,
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    api.listInterviewApplications.mockResolvedValue({
      data: [application],
      page: { hasMore: false, limit: 100, nextCursor: null },
    });
    api.listStories.mockResolvedValue({
      data: [],
      page: { hasMore: false, limit: 50, nextCursor: null },
    });
    api.listSessions.mockResolvedValue({
      data: [],
      page: { hasMore: false, limit: 50, nextCursor: null },
    });
    api.getDefenseMap.mockResolvedValue(defenseMap);
    api.createStory.mockResolvedValue(story);
  });

  it("shows defensibility warnings and saves a story with exact claim mappings", async () => {
    renderView();

    fireEvent.change(await screen.findByLabelText("Application"), {
      target: { value: application.id },
    });
    expect(
      await screen.findByText(/Strong claim lacks a ready defensible story\./),
    ).toBeVisible();
    expect(
      screen.getByText(/never sends a message or invents a missing fact/i),
    ).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Add STAR story" }));
    fireEvent.change(screen.getByLabelText("Story title"), {
      target: { value: story.title },
    });
    fireEvent.change(screen.getByLabelText("Situation"), {
      target: { value: story.situation },
    });
    fireEvent.change(screen.getByLabelText("Task"), {
      target: { value: story.task },
    });
    fireEvent.change(screen.getByLabelText("Action"), {
      target: { value: story.action },
    });
    fireEvent.change(screen.getByLabelText("Result"), {
      target: { value: story.result },
    });
    fireEvent.change(screen.getByLabelText("Personal contribution"), {
      target: { value: story.personalContribution },
    });
    fireEvent.change(
      screen.getByLabelText("Metric explanation (required for any number)"),
      { target: { value: story.metricExplanation } },
    );
    fireEvent.click(screen.getByLabelText(defenseMap.entries[0]!.claimText));
    fireEvent.click(
      screen.getByRole("button", { name: "Save grounded story" }),
    );

    expect(
      await screen.findByText(
        "Faster build feedback saved with exact claim and evidence revision pins.",
      ),
    ).toBeVisible();
    expect(api.createStory).toHaveBeenCalledWith(
      expect.objectContaining({
        applicationId: application.id,
        claimSelections: [
          expect.objectContaining({
            claimId: defenseMap.entries[0]!.claimId,
            fieldNames: expect.arrayContaining([
              "situation",
              "task",
              "action",
              "result",
            ]),
          }),
        ],
      }),
      expect.stringMatching(/^interview-web:/),
    );
  });

  it("renders explicit empty states without fictional practice data", async () => {
    renderView();

    expect(
      await screen.findByRole("heading", {
        name: "Practice from a roadmap built around you",
      }),
    ).toBeVisible();
    expect(await screen.findByTestId("roadmap-panel")).toBeVisible();
    expect(
      await screen.findByRole("heading", {
        name: "Application-linked practice",
      }),
    ).toBeVisible();
    expect(
      screen.getByText(
        /Select an application to open the defense map, STAR stories, and interview sessions/i,
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "No STAR stories yet" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "No interview sessions" }),
    ).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Application"), {
      target: { value: application.id },
    });

    expect(
      await screen.findByRole("heading", { name: "No STAR stories yet" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "No interview sessions" }),
    ).toBeVisible();
  });
});
