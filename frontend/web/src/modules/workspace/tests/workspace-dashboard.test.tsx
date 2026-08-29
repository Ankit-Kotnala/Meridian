import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { DashboardSummary } from "../server/dashboard-summary";
import { WorkspaceDashboard } from "../views/workspace-dashboard";

const unavailable = { kind: "unavailable" } as const;

function summary(overrides: Partial<DashboardSummary> = {}): DashboardSummary {
  return {
    activation: { jobs: unavailable, pendingImports: unavailable },
    applications: [],
    attention: [],
    attentionDegraded: false,
    growth: unavailable,
    jobHunt: unavailable,
    pipeline: unavailable,
    prepare: unavailable,
    record: {
      achievements: unavailable,
      evidence: unavailable,
      evidenceConfirmed: unavailable,
      experiences: unavailable,
      skills: unavailable,
    },
    resumes: unavailable,
    ...overrides,
  };
}

function count(value: number, atLeast = false) {
  return { atLeast, kind: "count", value } as const;
}

describe("real workspace dashboard", () => {
  it("renders stat cards without inventing metrics", () => {
    render(<WorkspaceDashboard displayName="Alex Morgan" onboardingComplete />);

    const overview = screen.getByRole("list", { name: "Home overview" });
    expect(within(overview).getAllByLabelText("Unavailable").length).toBe(4);
  });

  it("shows persisted record counts and marks unavailable sections explicitly", () => {
    render(
      <WorkspaceDashboard
        displayName="Alex Morgan"
        onboardingComplete
        summary={summary({
          record: {
            achievements: count(2),
            evidence: count(100, true),
            evidenceConfirmed: count(100, true),
            experiences: count(4),
            skills: unavailable,
          },
        })}
      />,
    );

    const overview = screen.getByRole("list", { name: "Home overview" });
    expect(
      within(overview).getByText("Roles").closest(".stat-card-tile"),
    ).toHaveTextContent("4");
    expect(
      within(overview).getByText("Skills").closest(".stat-card-tile"),
    ).toHaveTextContent("—");
  });

  it("lists review items that link to the place where the user decides", () => {
    render(
      <WorkspaceDashboard
        displayName="Alex Morgan"
        onboardingComplete
        summary={summary({
          attention: [
            {
              action: "Review",
              area: "Evidence",
              description: "2 evidence records are inferred or unsupported.",
              due: "—",
              href: "/evidence",
              id: "evidence-confirmation",
              label: "Confirm evidence before it is cited",
              tone: "warning",
            },
          ],
        })}
      />,
    );

    expect(
      screen.getByText("Confirm evidence before it is cited"),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Review" })).toHaveAttribute(
      "href",
      "/evidence",
    );
  });

  it("reports an all-clear review state without inventing activity", () => {
    render(<WorkspaceDashboard displayName="Alex Morgan" onboardingComplete />);

    expect(screen.getByText("You're all caught up")).toBeVisible();
  });

  it("warns that the review list may be incomplete when a source failed", () => {
    render(
      <WorkspaceDashboard
        displayName="Alex Morgan"
        onboardingComplete
        summary={summary({ attentionDegraded: true })}
      />,
    );

    expect(screen.getByText("Could not load your to-do list")).toBeVisible();
  });

  it("summarizes the application pipeline as accessible text", () => {
    render(
      <WorkspaceDashboard
        displayName="Alex Morgan"
        onboardingComplete
        summary={summary({
          pipeline: {
            atLeast: false,
            groups: [
              { count: 3, key: "exploring", label: "Exploring" },
              { count: 1, key: "applied", label: "Applied" },
              { count: 0, key: "interviewing", label: "Interviewing" },
              { count: 0, key: "offer", label: "Offer" },
              { count: 0, key: "closed", label: "Closed" },
            ],
            kind: "ready",
            openTasks: 2,
            total: 4,
          },
        })}
      />,
    );

    const pipeline = screen.getByRole("region", {
      name: "Application pipeline",
    });
    expect(
      within(pipeline).getByText(
        /4 tracked applications\. Exploring: 3, Applied: 1\./,
      ),
    ).toBeInTheDocument();
    expect(within(pipeline).getByText(/2 open tasks/)).toBeVisible();
  });

  it("states that the pipeline is unavailable instead of showing an empty one", () => {
    render(<WorkspaceDashboard displayName="Alex Morgan" onboardingComplete />);

    expect(
      screen.getByText(/application pipeline could not be loaded/i),
    ).toBeVisible();
  });
});

describe("workspace activation gate", () => {
  it("replaces the workspace with an upload gate when nothing exists yet", () => {
    render(
      <WorkspaceDashboard
        displayName="Sam Rivera"
        onboardingComplete
        summary={summary({
          record: {
            achievements: count(0),
            evidence: count(0),
            evidenceConfirmed: count(0),
            experiences: count(0),
            skills: count(0),
          },
        })}
      />,
    );

    expect(
      screen.getByRole("heading", {
        name: "Start with your resume or build your profile by hand.",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: /Upload your resume/ }),
    ).toHaveAttribute("href", "/resume-health/account");
    expect(
      screen.getByRole("link", { name: /Build it manually instead/ }),
    ).toHaveAttribute("href", "/career-profile");
    expect(
      screen.queryByRole("list", { name: "Home overview" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: "Application pipeline" }),
    ).not.toBeInTheDocument();
  });

  it("does not gate an account that built its record without a resume", () => {
    render(
      <WorkspaceDashboard
        displayName="Sam Rivera"
        onboardingComplete
        summary={summary({
          record: {
            achievements: count(0),
            evidence: count(0),
            evidenceConfirmed: count(0),
            experiences: count(2),
            skills: count(0),
          },
        })}
      />,
    );

    expect(
      screen.queryByRole("heading", {
        name: "Start with your resume or build your profile by hand.",
      }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Home overview" })).toBeVisible();
  });

  it("does not gate before onboarding is finished", () => {
    render(
      <WorkspaceDashboard
        displayName="Sam Rivera"
        onboardingComplete={false}
        summary={summary({
          record: {
            achievements: count(0),
            evidence: count(0),
            evidenceConfirmed: count(0),
            experiences: count(0),
            skills: count(0),
          },
        })}
      />,
    );

    expect(screen.getByRole("list", { name: "Home overview" })).toBeVisible();
  });

  it("keeps the record unavailable state out of the gate decision", () => {
    render(<WorkspaceDashboard displayName="Sam Rivera" onboardingComplete />);

    expect(
      screen.queryByRole("heading", {
        name: "Start with your resume or build your profile by hand.",
      }),
    ).not.toBeInTheDocument();
  });
});
