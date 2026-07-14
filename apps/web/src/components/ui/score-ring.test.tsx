import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ScoreRing } from "@/components/ui/score-ring";

describe("ScoreRing", () => {
  it("exposes a textual score to assistive technology", () => {
    render(<ScoreRing label="Resume Health" score={78} />);

    expect(
      screen.getByRole("img", { name: "Resume Health: 78/100" }),
    ).toBeInTheDocument();
  });

  it("clamps values to the supported range", () => {
    render(<ScoreRing label="Role Readiness" score={142} suffix="%" />);

    expect(
      screen.getByRole("img", { name: "Role Readiness: 100%" }),
    ).toBeInTheDocument();
  });
});
