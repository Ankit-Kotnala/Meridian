import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HeaderResumeScore } from "../components/header-resume-score";

describe("HeaderResumeScore", () => {
  it("shows the resume score as a clickable link to the full report, without a full disclaimer block", () => {
    render(
      <HeaderResumeScore
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
    expect(
      screen.getByRole("img", { name: "Resume Health Score: 73" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: /Resume Health Score 73 out of 100/i }),
    ).toHaveAttribute(
      "href",
      "/resume-health/account/report/00000000-0000-4000-8000-000000000030",
    );
    expect(
      screen.queryByText("Internal measure. Not an employer score."),
    ).not.toBeInTheDocument();
  });

  it("shows nothing when there is no report", () => {
    render(<HeaderResumeScore resumeHealth={{ kind: "error" }} />);

    expect(
      screen.queryByRole("img", { name: /Resume Health Score/i }),
    ).not.toBeInTheDocument();
  });
});
