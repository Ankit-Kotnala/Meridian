import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { DashboardSummary } from "../server/dashboard-summary";
import { WorkspaceDashboard } from "../views/workspace-dashboard";

const unavailable = { kind: "unavailable" } as const;

function summary(overrides: Partial<DashboardSummary> = {}): DashboardSummary {
  return {
    activation: { jobs: unavailable, pendingImports: unavailable },
    attention: [],
    attentionDegraded: false,
    pipeline: unavailable,
    record: {
      achievements: unavailable,
      evidence: unavailable,
      experiences: unavailable,
      skills: unavailable,
    },
    ...overrides,
  };
}

function count(value: number, atLeast = false) {
  return { atLeast, kind: "count", value } as const;
}

describe("real workspace dashboard", () => {
  it("renders account state and an honest empty resume view without metrics", () => {
    render(<WorkspaceDashboard displayName="Alex Morgan" onboardingComplete />);

    expect(
      screen.getByRole("heading", {
        name: "Welcome to your Rezumi workspace, Alex Morgan.",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "No resume data yet" }),
    ).toBeVisible();
    expect(screen.getByText(/upload a real PDF or DOCX/i)).toBeVisible();
    expect(screen.queryByText(/ATS score/i)).not.toBeInTheDocument();
  });

  it("renders a persisted report summary without demo metrics", () => {
    render(
      <WorkspaceDashboard
        displayName="Alex Morgan"
        onboardingComplete
        resumeHealth={{
          analysisId: "00000000-0000-4000-8000-000000000030",
          disclaimer: "Internal measure. Not an employer score.",
          filename: "fictional.pdf",
          kind: "report",
          score: 73,
          scoreBand: "developing",
        }}
      />,
    );
    expect(
      screen.getByRole("img", { name: "Resume Health Score: 73/100" }),
    ).toBeVisible();
    expect(
      screen.getByText("Internal measure. Not an employer score."),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: /open full report/i }),
    ).toHaveAttribute(
      "href",
      "/resume-health/account/report/00000000-0000-4000-8000-000000000030",
    );
  });

  it("renders an explicit failure state when persisted resume data is unavailable", () => {
    render(
      <WorkspaceDashboard
        displayName="Alex Morgan"
        onboardingComplete
        resumeHealth={{ kind: "error" }}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Resume Health unavailable",
    );
    expect(screen.getByText(/No document was changed/i)).toBeVisible();
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
            experiences: count(4),
            skills: unavailable,
          },
        })}
      />,
    );

    const records = screen.getByRole("region", { name: "Your career record" });
    expect(
      within(records).getByRole("link", { name: /Experiences/ }),
    ).toHaveTextContent("4");
    expect(
      within(records).getByRole("link", { name: /Evidence/ }),
    ).toHaveTextContent("100+");
    expect(within(records).getByLabelText("Unavailable")).toBeVisible();
    expect(
      within(records).getByText("Count unavailable right now"),
    ).toBeVisible();
  });

  it("lists review items that link to the place where the user decides", () => {
    render(
      <WorkspaceDashboard
        displayName="Alex Morgan"
        onboardingComplete
        summary={summary({
          attention: [
            {
              description: "2 evidence records are inferred or unsupported.",
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
      screen.getByRole("link", {
        name: /Confirm evidence before it is cited/,
      }),
    ).toHaveAttribute("href", "/evidence");
  });

  it("reports an all-clear review state without inventing activity", () => {
    render(<WorkspaceDashboard displayName="Alex Morgan" onboardingComplete />);

    expect(screen.getByText("Nothing is waiting on you")).toBeVisible();
  });

  it("warns that the review list may be incomplete when a source failed", () => {
    render(
      <WorkspaceDashboard
        displayName="Alex Morgan"
        onboardingComplete
        summary={summary({ attentionDegraded: true })}
      />,
    );

    expect(
      screen.getByText("No reviewable items could be loaded"),
    ).toBeVisible();
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

  it("prioritizes starting the career record when no experience exists yet", () => {
    render(
      <WorkspaceDashboard
        displayName="Alex Morgan"
        onboardingComplete
        resumeHealth={{
          analysisId: "00000000-0000-4000-8000-000000000030",
          disclaimer: "Internal measure. Not an employer score.",
          filename: "fictional.pdf",
          kind: "report",
          score: 73,
          scoreBand: "developing",
        }}
        summary={summary({
          record: {
            achievements: count(0),
            evidence: count(0),
            experiences: count(0),
            skills: count(0),
          },
        })}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Start your career record" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: /Add your first role/ }),
    ).toHaveAttribute("href", "/career-profile");
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
            experiences: count(0),
            skills: count(0),
          },
        })}
      />,
    );

    expect(
      screen.getByRole("heading", {
        name: "Add your resume to activate your workspace.",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: /Upload your resume/ }),
    ).toHaveAttribute("href", "/resume-health/account");
    expect(
      screen.getByRole("link", { name: /Build it manually instead/ }),
    ).toHaveAttribute("href", "/career-profile");
    expect(
      screen.queryByRole("region", { name: "Your career record" }),
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
            experiences: count(2),
            skills: count(0),
          },
        })}
      />,
    );

    expect(
      screen.queryByRole("heading", {
        name: "Add your resume to activate your workspace.",
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Your career record" }),
    ).toBeVisible();
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
            experiences: count(0),
            skills: count(0),
          },
        })}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Finish your account setup" }),
    ).toBeVisible();
  });

  it("keeps the record unavailable state out of the gate decision", () => {
    render(<WorkspaceDashboard displayName="Sam Rivera" onboardingComplete />);

    expect(
      screen.queryByRole("heading", {
        name: "Add your resume to activate your workspace.",
      }),
    ).not.toBeInTheDocument();
  });
});
