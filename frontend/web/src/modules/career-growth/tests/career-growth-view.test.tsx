import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  CareerGrowthInsights,
  CareerHealth,
  CareerReview,
  DevelopmentItem,
  Goal,
} from "../api/types";
import {
  CAREER_HEALTH_DISCLAIMER,
  CareerGrowthView,
} from "../views/career-growth-view";

const api = vi.hoisted(() => ({
  analyzeCareerHealth: vi.fn(),
  conflict: new Error("conflict"),
  createCareerReview: vi.fn(),
  createDevelopmentItem: vi.fn(),
  createGoal: vi.fn(),
  createMilestone: vi.fn(),
  deleteCareerHealth: vi.fn(),
  deleteCareerReview: vi.fn(),
  deleteDevelopmentItem: vi.fn(),
  deleteGoal: vi.fn(),
  deleteMilestone: vi.fn(),
  confirmRoleRoadmap: vi.fn(),
  finalizeCareerReview: vi.fn(),
  getCareerHealth: vi.fn(),
  getCareerReview: vi.fn(),
  getCareerGrowthInsights: vi.fn(),
  getGoal: vi.fn(),
  getRoleRoadmap: vi.fn(),
  listCareerHealth: vi.fn(),
  listCareerReviews: vi.fn(),
  listDevelopmentItems: vi.fn(),
  listGoals: vi.fn(),
  reviseCareerReview: vi.fn(),
  updateDevelopmentItem: vi.fn(),
  updateGoal: vi.fn(),
  updateMilestone: vi.fn(),
}));

vi.mock("../api/career-growth-api", () => ({
  ...api,
  isVersionConflict: (error: unknown) => error === api.conflict,
}));

const page = <T,>(data: T[]) => ({
  data,
  page: { hasMore: false, limit: 100, nextCursor: null },
});

const evidenceLink = {
  createdAt: "2026-07-24T11:00:00Z",
  evidenceId: "00000000-0000-4000-8000-000000009001",
  evidenceRevisedAt: "2026-07-23T11:00:00Z",
  evidenceRevisionId: "00000000-0000-4000-8000-000000009002",
  id: "00000000-0000-4000-8000-000000009003",
  revisionNumber: 3,
  statementSha256: "a".repeat(64),
  supportStatus: "current" as const,
  targetId: "00000000-0000-4000-8000-000000009004",
  targetKind: "goal" as const,
};

const goal = {
  createdAt: "2026-07-20T10:00:00Z",
  description: "Build an evidence-backed promotion case.",
  evidenceLinks: [evidenceLink],
  id: evidenceLink.targetId,
  milestones: [],
  status: "active",
  targetDate: "2026-12-31",
  title: "Prepare promotion case",
  updatedAt: "2026-07-24T10:00:00Z",
  version: 2,
} satisfies Goal;

const developmentItem = {
  completedAt: null,
  createdAt: "2026-07-20T10:00:00Z",
  description: "Complete the accessibility learning plan.",
  evidenceLinks: [],
  id: "00000000-0000-4000-8000-000000009010",
  kind: "learning",
  status: "in_progress",
  targetDate: "2026-10-01",
  title: "Accessibility systems",
  updatedAt: "2026-07-24T10:00:00Z",
  version: 1,
} satisfies DevelopmentItem;

const reviewVersion: CareerReview["currentVersion"] = {
  achievements: "Shipped an accessible workflow.",
  changeReason: "Initial review",
  contentSha256: "b".repeat(64),
  createdAt: "2026-07-20T10:00:00Z",
  evidenceLinks: [],
  growthAreas: "Delegation",
  id: "00000000-0000-4000-8000-000000009021",
  materialChange: true,
  nextFocus: "Mentor another engineer",
  reviewId: "00000000-0000-4000-8000-000000009020",
  status: "draft",
  summary: "A quarter of measurable delivery.",
  supersedesVersionId: null,
  title: "Q2 career review",
  versionNumber: 1,
};

const review = {
  cadence: "quarterly",
  createdAt: "2026-07-20T10:00:00Z",
  currentVersion: reviewVersion,
  history: [reviewVersion],
  id: "00000000-0000-4000-8000-000000009020",
  latestStatus: "draft",
  latestVersionId: "00000000-0000-4000-8000-000000009021",
  latestVersionNumber: 1,
  periodEnd: "2026-06-30",
  periodStart: "2026-04-01",
  updatedAt: "2026-07-20T10:00:00Z",
  version: 1,
} satisfies CareerReview;

const careerHealth = {
  applicableComponentCount: 4,
  applicableWeightBasisPoints: 8000,
  components: [
    {
      applicable: true,
      configuredWeightBasisPoints: 2500,
      contributionBasisPoints: 1900,
      dimension: "goal_progress",
      explanation: "Active goals contain current milestones.",
      id: "00000000-0000-4000-8000-000000009031",
      scoreBasisPoints: 7600,
    },
  ],
  configurationSnapshot: { minimumApplicableComponents: 2 },
  configurationVersion: "career-health-default/1",
  createdAt: "2026-07-24T12:00:00Z",
  disclaimer: CAREER_HEALTH_DISCLAIMER,
  displayScore: 76,
  engineVersion: "career-health/1.0.0",
  featureSchemaVersion: "career-health-features/1",
  findings: [
    {
      code: "review_due",
      id: "00000000-0000-4000-8000-000000009032",
      message: "A review is due soon.",
      severity: "information",
    },
  ],
  formulaSnapshot: { aggregation: "weighted_applicable_components" },
  id: "00000000-0000-4000-8000-000000009030",
  inputSnapshot: { purposeLimited: true },
  insufficientReason: null,
  label: "developing",
  rawScoreBasisPoints: 7600,
  snapshotSha256: "c".repeat(64),
  status: "complete",
} satisfies CareerHealth;

const growthInsights = {
  achievements: [
    {
      evidenceId: evidenceLink.evidenceId,
      evidenceRevisionId: evidenceLink.evidenceRevisionId,
      evidenceType: "achievement",
      revisedAt: "2026-07-23T11:00:00Z",
      revisionNumber: 3,
      skillIds: ["00000000-0000-4000-8000-000000009040"],
      statement: "The owner confirmed an evidence-backed fictional result.",
      strength: "confirmed",
      title: "Verified fictional achievement",
    },
  ],
  annualResumeRefreshes: [],
  promotionReadiness: {
    checks: [
      "eligible_achievement_evidence",
      "skill_evidence_coverage",
      "evidence_backed_milestones",
      "promotion_plan",
      "finalized_career_review",
      "annual_resume_refresh",
    ].map((code) => ({
      code,
      evidenceCount: 0,
      evidenceIds: [],
      explanation: "Owner action remains.",
      label: code.replaceAll("_", " "),
      status: "needs_action" as const,
    })),
    disclaimer:
      "Promotion Readiness summarizes Rezumi preparation signals from current eligible evidence and owner-maintained records. It is not an employer decision, hiring probability, promotion guarantee, or assessment of job-market value.",
    generatedAt: "2026-07-24T12:00:00Z",
    status: "building",
  },
  skills: [
    {
      category: "technical",
      evidenceCount: 1,
      evidenceIds: [evidenceLink.evidenceId],
      latestEvidenceAt: "2026-07-23T11:00:00Z",
      name: "Accessibility systems",
      proficiency: "advanced",
      skillId: "00000000-0000-4000-8000-000000009040",
    },
  ],
} satisfies CareerGrowthInsights;

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

async function openGrowthTab(name: string) {
  fireEvent.click(await screen.findByRole("tab", { name }));
}

describe("Career Growth view", () => {
  beforeAll(() => {
    HTMLDialogElement.prototype.showModal = function showModal() {
      this.setAttribute("open", "");
    };
    HTMLDialogElement.prototype.close = function close() {
      this.removeAttribute("open");
    };
  });

  beforeEach(() => {
    vi.clearAllMocks();
    api.listGoals.mockResolvedValue(page([goal]));
    api.listDevelopmentItems.mockResolvedValue(page([developmentItem]));
    api.listCareerReviews.mockResolvedValue(page([review]));
    api.listCareerHealth.mockResolvedValue(page([careerHealth]));
    api.getCareerGrowthInsights.mockResolvedValue(growthInsights);
    api.getRoleRoadmap.mockResolvedValue(null);
    api.finalizeCareerReview.mockResolvedValue({
      ...review,
      currentVersion: { ...review.currentVersion, status: "finalized" },
      history: [{ ...review.currentVersion, status: "finalized" }],
      latestStatus: "finalized",
      version: 2,
    });
  });

  it("renders complete, empty, and score explanation states without demo metrics", async () => {
    render(<CareerGrowthView />);

    expect(
      await screen.findByRole("heading", {
        name: "Evidence-backed preparation checklist",
      }),
    ).toBeVisible();
    expect(screen.getByText("Verified fictional achievement")).toBeVisible();
    expect(
      screen.getByRole("table", {
        name: /Documented skills and their eligible evidence coverage/i,
      }),
    ).toBeVisible();
    expect(
      screen.queryByText(/likely to be promoted/i),
    ).not.toBeInTheDocument();

    await openGrowthTab("Career Health");
    expect(
      await screen.findByRole("heading", {
        name: "A transparent maintenance signal",
      }),
    ).toBeVisible();
    const score = screen.getByRole("heading", { name: /76\/100/ });
    const scoreSection = score.closest("section");
    expect(scoreSection).not.toBeNull();
    expect(
      within(scoreSection!).getByText(CAREER_HEALTH_DISCLAIMER),
    ).toBeVisible();
    expect(
      screen.getByRole("table", {
        name: /Career Health component scores/i,
      }),
    ).toBeVisible();

    await openGrowthTab("Goals & plans");
    expect(screen.getByText("Prepare promotion case")).toBeVisible();
    expect(screen.getAllByText("Accessibility systems")).not.toHaveLength(0);
    expect(screen.getAllByText("Q2 career review")).not.toHaveLength(0);

    api.listGoals.mockResolvedValueOnce(page([]));
    api.listDevelopmentItems.mockResolvedValueOnce(page([]));
    api.listCareerReviews.mockResolvedValueOnce(page([]));
    api.listCareerHealth.mockResolvedValueOnce(page([]));
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));

    await openGrowthTab("Goals & plans");
    expect(
      await screen.findByRole("heading", { name: "No career goals yet" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", {
        name: "No development plan items yet",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "No career reviews yet" }),
    ).toBeVisible();

    await openGrowthTab("Career Health");
    expect(
      await screen.findByRole("heading", {
        name: "No Career Health snapshot yet",
      }),
    ).toBeVisible();
  });

  it("shows insufficient data without rendering a fabricated score", async () => {
    api.listCareerHealth.mockResolvedValue(
      page([
        {
          ...careerHealth,
          applicableComponentCount: 1,
          applicableWeightBasisPoints: 2500,
          displayScore: null,
          insufficientReason:
            "At least two applicable components are required.",
          label: "insufficient_data",
          rawScoreBasisPoints: null,
          status: "insufficient_data",
        },
      ]),
    );

    render(<CareerGrowthView />);

    await openGrowthTab("Career Health");
    expect(
      await screen.findByRole("heading", { name: "Insufficient data" }),
    ).toBeVisible();
    expect(
      screen.getByText("At least two applicable components are required."),
    ).toBeVisible();
    expect(screen.queryByText(/\/100/)).not.toBeInTheDocument();
    expect(screen.getByText(CAREER_HEALTH_DISCLAIMER)).toBeVisible();
  });

  it("requires confirmation for immutable finalization and authoritative reload after conflicts", async () => {
    api.updateGoal.mockRejectedValue(api.conflict);
    render(<CareerGrowthView />);
    await openGrowthTab("Goals & plans");
    await screen.findByText("Prepare promotion case");

    fireEvent.click(screen.getByText("Edit goal"));
    fireEvent.click(screen.getByRole("button", { name: "Save goal" }));

    expect(
      await screen.findByText(/changed in another session/i),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Reload authoritative data" }),
    ).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Finalize" }));
    expect(api.finalizeCareerReview).not.toHaveBeenCalled();
    expect(
      screen.getByRole("heading", { name: "Finalize this review version?" }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Finalize review" }));
    await waitFor(() =>
      expect(api.finalizeCareerReview).toHaveBeenCalledWith(
        review,
        expect.any(String),
      ),
    );
    const idempotencyKey = api.finalizeCareerReview.mock.calls[0]?.[1];
    expect(idempotencyKey).toMatch(/^[A-Za-z0-9._:-]{8,128}$/);
    expect(idempotencyKey?.length).toBeLessThanOrEqual(128);
    expect(
      await screen.findByText(/Q2 career review finalized/i),
    ).toBeVisible();
    expect(screen.getByText("Immutable history (1)")).toBeVisible();
  });

  it("keeps form data and reuses the idempotency key when goal creation is retried", async () => {
    const createdGoal = {
      ...goal,
      id: "00000000-0000-4000-8000-000000009098",
      title: "Build a mentoring practice",
      version: 1,
    };
    api.createGoal
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(createdGoal);
    render(<CareerGrowthView />);
    await openGrowthTab("Goals & plans");
    await screen.findByText("Prepare promotion case");

    fireEvent.click(screen.getByText("Add a career goal"));
    const title = screen.getByLabelText("Goal title");
    fireEvent.change(title, {
      target: { value: "Build a mentoring practice" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add goal" }));

    expect(
      await screen.findByText("The goal could not be added."),
    ).toBeVisible();
    expect(title).toHaveValue("Build a mentoring practice");
    fireEvent.click(screen.getByRole("button", { name: "Add goal" }));

    expect(
      await screen.findByText(
        "Build a mentoring practice added as a career goal.",
      ),
    ).toBeVisible();
    expect(api.createGoal).toHaveBeenCalledTimes(2);
    expect(api.createGoal.mock.calls[0]?.[1]).toEqual(
      api.createGoal.mock.calls[1]?.[1],
    );
  });

  it("refreshes annual resume insights after a completed plan item is created", async () => {
    const annualRefreshId = "00000000-0000-4000-8000-000000009096";
    const annualRefresh = {
      ...developmentItem,
      completedAt: "2026-07-24T12:30:00Z",
      evidenceLinks: [
        {
          ...evidenceLink,
          id: "00000000-0000-4000-8000-000000009095",
          targetId: annualRefreshId,
          targetKind: "development_item",
        },
      ],
      id: annualRefreshId,
      kind: "annual_resume_refresh",
      status: "completed",
      title: "Refresh the evidence-backed resume",
      version: 1,
    } satisfies DevelopmentItem;
    api.createDevelopmentItem.mockResolvedValue(annualRefresh);
    api.getCareerGrowthInsights
      .mockResolvedValueOnce(growthInsights)
      .mockResolvedValue({
        ...growthInsights,
        annualResumeRefreshes: [annualRefresh],
      });

    render(<CareerGrowthView />);
    await openGrowthTab("Goals & plans");
    await screen.findByText("Prepare promotion case");

    const summary = screen.getByText("Add a development plan item", {
      exact: true,
    });
    const details = summary.closest("details");
    expect(details).not.toBeNull();
    fireEvent.click(summary);
    const form = within(details!);
    fireEvent.change(form.getByLabelText("Title"), {
      target: { value: annualRefresh.title },
    });
    fireEvent.change(form.getByLabelText("Kind"), {
      target: { value: "annual_resume_refresh" },
    });
    fireEvent.change(form.getByLabelText("Status"), {
      target: { value: "completed" },
    });
    fireEvent.change(form.getByLabelText(/^Evidence IDs/), {
      target: { value: evidenceLink.evidenceId },
    });
    fireEvent.click(form.getByRole("button", { name: "Add plan item" }));

    expect(
      await screen.findByText(
        `${annualRefresh.title} added to your development plan.`,
      ),
    ).toBeVisible();
    await openGrowthTab("Preparation");
    const workflowHeading = screen.getByRole("heading", {
      name: "Annual resume refresh workflow",
    });
    const workflow = workflowHeading.parentElement;
    expect(workflow).not.toBeNull();
    const workflowItem = await within(workflow!).findByRole("listitem");
    expect(within(workflowItem).getByText(annualRefresh.title)).toBeVisible();
    expect(within(workflowItem).getByText("Completed")).toBeVisible();
    expect(workflowItem).toHaveTextContent("1 evidence link(s)");
    expect(api.getCareerGrowthInsights).toHaveBeenCalledTimes(2);
    expect(api.listDevelopmentItems).toHaveBeenCalledTimes(1);
  });

  it("continues a paginated collection without duplicating the initial page", async () => {
    const additionalGoal = {
      ...goal,
      id: "00000000-0000-4000-8000-000000009097",
      title: "Second page goal",
    };
    api.listGoals
      .mockResolvedValueOnce({
        data: [goal],
        page: { hasMore: true, limit: 100, nextCursor: "next-goal-page" },
      })
      .mockResolvedValueOnce(page([additionalGoal]));

    render(<CareerGrowthView />);
    await openGrowthTab("Goals & plans");
    fireEvent.click(
      await screen.findByRole("button", { name: "Load more goals" }),
    );

    expect(await screen.findByText("Second page goal")).toBeVisible();
    expect(screen.getAllByText("Prepare promotion case")).toHaveLength(1);
    expect(api.listGoals.mock.calls[1]?.[0]).toEqual(
      expect.objectContaining({ cursor: "next-goal-page" }),
    );
  });

  it("aborts superseded loads and ignores a late response", async () => {
    const stale = deferred<ReturnType<typeof page<Goal>>>();
    const latestGoal = {
      ...goal,
      id: "00000000-0000-4000-8000-000000009099",
      title: "Latest goal",
    };
    const latest = deferred<ReturnType<typeof page<Goal>>>();
    const signals: AbortSignal[] = [];
    api.listGoals
      .mockImplementationOnce(() => page([goal]))
      .mockImplementationOnce((options?: { signal?: AbortSignal }) => {
        if (options?.signal) signals.push(options.signal);
        return stale.promise;
      })
      .mockImplementationOnce((options?: { signal?: AbortSignal }) => {
        if (options?.signal) signals.push(options.signal);
        return latest.promise;
      });

    render(<CareerGrowthView />);
    await openGrowthTab("Goals & plans");
    const reload = await screen.findByRole("button", { name: "Refresh" });

    act(() => {
      reload.click();
      reload.click();
    });
    expect(signals[0]?.aborted).toBe(true);

    await act(async () => {
      latest.resolve(page([latestGoal]));
    });
    await openGrowthTab("Goals & plans");
    expect(await screen.findByText("Latest goal")).toBeVisible();

    await act(async () => {
      stale.resolve(page([{ ...goal, title: "Stale goal" }]));
    });
    expect(screen.queryByText("Stale goal")).not.toBeInTheDocument();
    expect(screen.getByText("Latest goal")).toBeVisible();
  });

  it("renders a retryable initial failure", async () => {
    const offline = new Error("offline");
    api.listGoals.mockRejectedValueOnce(offline);
    api.listDevelopmentItems.mockRejectedValueOnce(offline);
    api.listCareerReviews.mockRejectedValueOnce(offline);
    api.listCareerHealth.mockRejectedValueOnce(offline);
    api.getCareerGrowthInsights.mockRejectedValueOnce(offline);
    render(<CareerGrowthView />);

    expect(
      await screen.findByRole("heading", {
        name: "Career Growth unavailable",
      }),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Try again" })).toBeVisible();
  });

  it("marks already-known roadmap skills and confirms the selection", async () => {
    api.getRoleRoadmap.mockResolvedValue({
      roleTitle: "AI Engineer",
      stages: [
        {
          stage: "Foundations",
          skills: [
            {
              name: "Python",
              why: "Most ML tooling is Python-first.",
              howToStart: "Build one small script end to end.",
              alreadyDemonstrated: true,
              library: { freeCourses: [], notes: [], paidCourses: [] },
            },
            {
              name: "Prompt engineering",
              why: "Directly shapes LLM output quality.",
              howToStart: "Iterate on one prompt against a fixed test set.",
              alreadyDemonstrated: false,
              library: { freeCourses: [], notes: [], paidCourses: [] },
            },
          ],
        },
      ],
    });
    api.confirmRoleRoadmap.mockResolvedValue({ created: [developmentItem] });

    render(<CareerGrowthView />);
    await openGrowthTab("Roadmap");

    expect(
      await screen.findByRole("heading", { name: "Path to AI Engineer" }),
    ).toBeVisible();
    expect(
      screen.getAllByText("Evidence documented").length,
    ).toBeGreaterThanOrEqual(1);

    fireEvent.click(
      screen.getByRole("button", { name: "Add selected to growth plan" }),
    );

    await waitFor(() =>
      expect(api.confirmRoleRoadmap).toHaveBeenCalledWith(
        expect.objectContaining({
          roleTitle: "AI Engineer",
          includedSkillNames: ["Prompt engineering"],
        }),
      ),
    );
    expect(
      await screen.findByText(/development item added to your plan/i),
    ).toBeVisible();
  });
});
