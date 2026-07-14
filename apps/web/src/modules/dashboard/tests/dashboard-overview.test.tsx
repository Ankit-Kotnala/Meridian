import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DashboardOverview } from "@/modules/dashboard";

describe("DashboardOverview", () => {
  it("labels the preview data and score limitations", () => {
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
      screen.getByRole("img", { name: "Resume Health Score: 78/100" }),
    ).toBeInTheDocument();
  });

  it("provides a text alternative for the pipeline chart", () => {
    render(<DashboardOverview />);
    expect(
      screen.getByRole("img", {
        name: /pipeline summary: 12 saved, 24 applied, 5 interview, 2 offer/i,
      }),
    ).toBeInTheDocument();
  });
});
