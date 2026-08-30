import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ResumeScoreSummary } from "../components/resume-score-summary";

describe("ResumeScoreSummary", () => {
  it("shows the resume score as a clickable link to the full report, without a full disclaimer block", () => {
    render(
      <ResumeScoreSummary
        resumeHealth={{
          analysisId: "00000000-0000-4000-8000-000000000030",
          disclaimer: "Internal measure. Not an employer score.",
          documentId: "00000000-0000-4000-8000-000000000031",
          filename: "fictional.pdf",
          kind: "report",
          score: 73,
          scoreBand: "developing",
          snapshotId: "00000000-0000-4000-8000-000000000032",
        }}
      />,
    );
    const link = screen.getByRole("link", {
      name: /Resume Health Score 73 out of 100/i,
    });
    expect(link).toHaveAttribute(
      "href",
      "/resume-health/account/report/00000000-0000-4000-8000-000000000030",
    );
    expect(link).toHaveTextContent("73% overall");
    expect(
      screen.queryByText("Internal measure. Not an employer score."),
    ).not.toBeInTheDocument();
  });

  it("shows nothing when there is no report", () => {
    render(<ResumeScoreSummary resumeHealth={{ kind: "error" }} />);

    expect(
      screen.queryByRole("link", { name: /Resume Health Score/i }),
    ).not.toBeInTheDocument();
  });
});
