import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CareerGrowthInsights } from "../api/types";
import { GrowthInsightsPanel } from "../components/growth-insights-panel";

const api = vi.hoisted(() => ({
  getRoleRoadmap: vi.fn(),
}));

vi.mock("../api/career-growth-api", () => api);

const insights = {
  achievements: [
    {
      evidenceId: "00000000-0000-4000-8000-000000009001",
      evidenceRevisionId: "00000000-0000-4000-8000-000000009002",
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
      {
        code: "skill_evidence_coverage",
        evidenceCount: 1,
        evidenceIds: ["00000000-0000-4000-8000-000000009001"],
        explanation:
          "1 of 1 documented skill(s) have currently eligible evidence.",
        label: "Skill-to-evidence coverage",
        status: "supported",
      },
      {
        code: "promotion_plan",
        evidenceCount: 0,
        evidenceIds: [],
        explanation: "Create a promotion-preparation development item.",
        label: "Promotion preparation plan",
        status: "needs_action",
      },
    ],
    disclaimer:
      "Promotion Readiness summarizes Rezumi preparation signals from current eligible evidence and owner-maintained records. It is not an employer decision, hiring probability, promotion guarantee, or assessment of job-market value.",
    generatedAt: "2026-07-24T12:00:00Z",
    status: "building",
  },
  skills: [
    {
      category: "technical",
      evidenceCount: 1,
      evidenceIds: ["00000000-0000-4000-8000-000000009001"],
      latestEvidenceAt: "2026-07-23T11:00:00Z",
      name: "Model serving",
      proficiency: "advanced",
      skillId: "00000000-0000-4000-8000-000000009040",
    },
  ],
} satisfies CareerGrowthInsights;

describe("GrowthInsightsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getRoleRoadmap.mockResolvedValue(null);
  });

  it("keeps promotion and skill tables while refusing market ranking language", async () => {
    render(<GrowthInsightsPanel insights={insights} />);

    expect(
      await screen.findByRole("heading", {
        name: "Achievement and promotion preparation",
      }),
    ).toBeVisible();
    expect(
      screen.getByTestId("promotion-readiness-disclaimer"),
    ).toHaveTextContent(
      /not an employer decision, hiring probability, promotion guarantee, or assessment of job-market value/i,
    );
    fireEvent.click(screen.getByText(/View full preparation checklist/i));
    expect(
      screen.getByRole("table", {
        name: "Promotion preparation checks, evidence state, and next action",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("table", {
        name: "Documented skills and their eligible evidence coverage",
      }),
    ).toBeVisible();
    expect(
      screen.queryByText(/likely to be promoted/i),
    ).not.toBeInTheDocument();
    expect(
      await screen.findByRole("heading", {
        name: "No target-role path to compare yet",
      }),
    ).toBeVisible();
  });

  it("compares evidenced skills against the curated target-role path", async () => {
    api.getRoleRoadmap.mockResolvedValue({
      roleTitle: "AI Engineer",
      stages: [
        {
          skills: [
            {
              alreadyDemonstrated: false,
              howToStart: "Deploy a bounded inference service.",
              library: { freeCourses: [], notes: [], paidCourses: [] },
              name: "Model serving",
              why: "Production roles require safe inference delivery.",
            },
            {
              alreadyDemonstrated: false,
              howToStart:
                "Explain one evaluated model from your Career Record.",
              library: { freeCourses: [], notes: [], paidCourses: [] },
              name: "Model evaluation",
              why: "Reliable systems need measurable model quality.",
            },
          ],
          stage: "Production foundations",
        },
      ],
    });
    render(<GrowthInsightsPanel insights={insights} />);

    expect(
      await screen.findByRole("heading", {
        name: /AI Engineer path · 1 evidenced · 1 gaps/,
      }),
    ).toBeVisible();
    expect(screen.getByText("Evidence found")).toBeVisible();
    expect(screen.getByText("Gap on this path")).toBeVisible();
    fireEvent.click(screen.getByText(/View full preparation checklist/i));
    expect(
      screen.getByText("Create a promotion-preparation development item."),
    ).toBeVisible();
  });
});
