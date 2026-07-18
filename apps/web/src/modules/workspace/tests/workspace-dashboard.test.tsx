import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkspaceDashboard } from "../views/workspace-dashboard";

describe("real workspace dashboard", () => {
  it("renders account state and an honest empty resume view without metrics", () => {
    render(<WorkspaceDashboard displayName="Alex Morgan" onboardingComplete />);

    expect(
      screen.getByRole("heading", {
        name: "Welcome to your CareerOS workspace, Alex Morgan.",
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
});
