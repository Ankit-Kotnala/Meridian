import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

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

describe("RoadmapPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getRoleRoadmap.mockResolvedValue(roadmap);
    api.confirmRoleRoadmap.mockResolvedValue({ created: [{}] });
  });

  it("renders a compact staged path and reveals stop details on demand", async () => {
    render(<RoadmapPanel />);

    expect(
      await screen.findByRole("heading", { name: "Your path to AI Engineer" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Production foundations" }),
    ).toHaveAttribute("href", "#roadmap-stage-0");
    expect(screen.getAllByText("Evidence found")).toHaveLength(2);
    expect(screen.getByText("Suggested focus")).toBeVisible();
    for (const label of screen.getAllByText("Start here:")) {
      expect(label).not.toBeVisible();
    }

    const evaluationStop = screen.getByRole("button", {
      name: "Model evaluation",
    });
    expect(evaluationStop).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(evaluationStop);

    expect(evaluationStop).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByText("Reliable systems need measurable model quality."),
    ).toBeVisible();
    expect(
      screen.getByText("Explain one evaluated model from your Career Record."),
    ).toBeVisible();
    expect(
      screen.getByText("Production roles require safe inference delivery."),
    ).not.toBeVisible();
  });

  it("reveals a stop on hover when the pointer can hover", async () => {
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = vi.fn().mockReturnValue({
      addEventListener: vi.fn(),
      matches: true,
      media: "(hover: hover) and (pointer: fine)",
      removeEventListener: vi.fn(),
    }) as unknown as typeof window.matchMedia;
    try {
      render(<RoadmapPanel />);
      const evaluationStop = await screen.findByRole("button", {
        name: "Model evaluation",
      });

      fireEvent.mouseEnter(evaluationStop.closest("li")!);

      expect(evaluationStop).toHaveAttribute("aria-expanded", "true");
      expect(
        screen.getByText("Reliable systems need measurable model quality."),
      ).toBeVisible();
      expect(
        screen.getByText("Production roles require safe inference delivery."),
      ).not.toBeVisible();
    } finally {
      window.matchMedia = originalMatchMedia;
    }
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
