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
    expect(
      screen.getByText(/sample scores or invented activity/i),
    ).toBeVisible();
    expect(screen.queryByText(/ATS score/i)).not.toBeInTheDocument();
  });
});
