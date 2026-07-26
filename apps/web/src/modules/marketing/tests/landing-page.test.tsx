import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LandingPage } from "@/modules/marketing";

describe("LandingPage", () => {
  it("states the evidence-first product promise and responsible limits", () => {
    render(<LandingPage />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /the system of record behind your career/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("No unsupported claims")).toBeInTheDocument();
    expect(screen.getByText("Grounded by default")).toBeInTheDocument();
    expect(screen.getByText(/not a customer testimonial/i)).toBeInTheDocument();
    expect(
      screen.getAllByText(/do not guarantee outcomes/i).length,
    ).toBeGreaterThan(0);
  });
});
