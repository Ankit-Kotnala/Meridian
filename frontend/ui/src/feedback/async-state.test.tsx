import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EmptyState, ErrorState, LoadingSkeleton } from "./async-state";

describe("asynchronous states", () => {
  it("announces loading without relying on animation", () => {
    render(<LoadingSkeleton />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByText("Loading content")).toBeInTheDocument();
  });

  it("shows useful empty-state copy", () => {
    render(
      <EmptyState
        description="Add an evidence record to begin."
        title="No evidence yet"
      />,
    );
    expect(
      screen.getByRole("heading", { name: "No evidence yet" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Add an evidence record to begin."),
    ).toBeInTheDocument();
  });

  it("allows a failed request to be retried", () => {
    const retry = vi.fn();
    render(<ErrorState onRetry={retry} />);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
  });
});
