import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DashboardOverview } from "@/modules/dashboard";

describe("DashboardOverview", () => {
  it("labels the fictional scenario and measurement limitations", () => {
    render(<DashboardOverview />);

    expect(
      screen.getByText(/fictional demo data · product preview only/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /not scores provided by an employer or applicant tracking system/i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "Follow the evidence into an output.",
      }),
    ).toBeInTheDocument();
  });

  it("explains the review state without fake metrics or activity feeds", () => {
    render(<DashboardOverview />);
    expect(
      screen.getByRole("heading", {
        name: "A material change waits for a person.",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Eligible source links")).toBeInTheDocument();
    expect(screen.queryByText(/pipeline summary/i)).not.toBeInTheDocument();
  });
});
