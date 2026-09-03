import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RoadmapPanel } from "../components/roadmap-panel";

const api = vi.hoisted(() => ({
  confirmRoleRoadmap: vi.fn(),
  getRoleRoadmap: vi.fn(),
}));

vi.mock("../api/career-growth-api", () => api);

const roadmap = {
  roleTitle: "AI Engineer",
  stages: [
    {
      skills: [
        {
          alreadyDemonstrated: true,
          howToStart: "Explain one evaluated model from your Career Record.",
          name: "Model evaluation",
          why: "Reliable systems need measurable model quality.",
        },
        {
          alreadyDemonstrated: false,
          howToStart: "Deploy a bounded inference service.",
          name: "Model serving",
          why: "Production roles require safe inference delivery.",
        },
      ],
      stage: "Production foundations",
    },
  ],
};

function mockPrefersHover() {
  const originalMatchMedia = window.matchMedia;
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    addEventListener: vi.fn(),
    matches: query.includes("hover"),
    media: query,
    removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia;
  return () => {
    window.matchMedia = originalMatchMedia;
  };
}

describe("RoadmapPanel", () => {
  let restoreMatchMedia: (() => void) | undefined;

  beforeEach(() => {
    restoreMatchMedia = mockPrefersHover();
    vi.clearAllMocks();
    api.getRoleRoadmap.mockResolvedValue(roadmap);
    api.confirmRoleRoadmap.mockResolvedValue({ created: [{}] });
  });

  afterEach(() => {
    restoreMatchMedia?.();
  });

  it("renders a compact staged path and reveals stop details on hover", async () => {
    render(<RoadmapPanel />);

    expect(
      await screen.findByRole("heading", { name: "Your path to AI Engineer" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: /Production foundations/i }),
    ).toHaveAttribute("href", "#roadmap-stage-0");
    expect(screen.getAllByText("Evidence found")).toHaveLength(1);
    expect(screen.getByText("Suggested focus")).toBeVisible();
    expect(screen.queryByText("Start here:")).not.toBeInTheDocument();

    const evaluationNode = (
      await screen.findByRole("heading", { name: "Model evaluation" })
    ).closest("[data-roadmap-node]")!;

    fireEvent.mouseEnter(evaluationNode);

    await waitFor(() => {
      expect(
        screen.getByText("Reliable systems need measurable model quality."),
      ).toBeVisible();
    });
    expect(
      screen.getByText("Explain one evaluated model from your Career Record."),
    ).toBeVisible();
    expect(
      screen.queryByText("Production roles require safe inference delivery."),
    ).not.toBeInTheDocument();
  });

  it("hides stop details when hover ends", async () => {
    render(<RoadmapPanel />);

    const evaluationNode = (
      await screen.findByRole("heading", { name: "Model evaluation" })
    ).closest("[data-roadmap-node]")!;

    fireEvent.mouseEnter(evaluationNode);
    await waitFor(() => {
      expect(
        screen.getByText("Reliable systems need measurable model quality."),
      ).toBeVisible();
    });

    fireEvent.mouseLeave(evaluationNode);
    await waitFor(() => {
      expect(
        screen.queryByText("Reliable systems need measurable model quality."),
      ).not.toBeInTheDocument();
    });
  });

  it("confirms only the selected development-plan skills", async () => {
    const onConfirmed = vi.fn();
    render(<RoadmapPanel onConfirmed={onConfirmed} />);

    await screen.findByRole("heading", { name: "Your path to AI Engineer" });

    const choices = screen.getAllByRole("checkbox");
    expect(choices[0]).not.toBeChecked();
    expect(choices[1]).toBeChecked();

    fireEvent.click(
      screen.getByRole("button", { name: "Add selected to growth plan" }),
    );

    expect(api.confirmRoleRoadmap).toHaveBeenCalledWith({
      includedSkillNames: ["Model serving"],
      roleTitle: "AI Engineer",
    });
    expect(
      await screen.findByText("1 development item added to your plan below."),
    ).toBeVisible();
    expect(onConfirmed).toHaveBeenCalledOnce();
  });

  it("offers the target-role setup path when no roadmap can be resolved", async () => {
    api.getRoleRoadmap.mockResolvedValue(null);
    render(<RoadmapPanel />);

    expect(
      await screen.findByRole("heading", {
        name: "We could not identify your role yet",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Review your resume role" }),
    ).toHaveAttribute("href", "/career-profile");
  });
});
