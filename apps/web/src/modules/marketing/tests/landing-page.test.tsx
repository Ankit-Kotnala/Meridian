import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LandingPage } from "@/modules/marketing";

describe("LandingPage", () => {
  it("states the evidence-first product promise and responsible limits", () => {
    render(<LandingPage />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /your career story, built on evidence/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("No made-up achievements")).toBeInTheDocument();
    expect(screen.getByText(/not a customer testimonial/i)).toBeInTheDocument();
    expect(
      screen.getAllByText(/do not guarantee outcomes/i).length,
    ).toBeGreaterThan(0);
  });
});
