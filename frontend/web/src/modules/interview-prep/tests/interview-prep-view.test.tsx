import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { InterviewPrepView } from "../views/interview-prep-view";

const router = vi.hoisted(() => ({
  push: vi.fn(),
  refresh: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => router,
}));

describe("Interview Prep view", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the skill journey without a practice lab", () => {
    render(
      <InterviewPrepView
        roadmapPanel={<div data-testid="roadmap-panel">Role roadmap</div>}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Interview readiness workspace" }),
    ).toBeVisible();
    expect(screen.getByTestId("roadmap-panel")).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Practice lab" }),
    ).not.toBeInTheDocument();
  });

  it("refreshes the route from the workspace header", () => {
    render(
      <InterviewPrepView
        roadmapPanel={<div data-testid="roadmap-panel">Role roadmap</div>}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    expect(router.refresh).toHaveBeenCalledOnce();
  });
});
