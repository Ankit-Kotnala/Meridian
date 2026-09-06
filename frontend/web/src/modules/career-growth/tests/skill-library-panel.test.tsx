import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { InterviewPrepWorkspaceMetricsProvider } from "@/shared/workspace/interview-prep-workspace-metrics";

import { SkillLibraryPanel } from "../components/skill-library-panel";

const navigation = vi.hoisted(() => ({
  skill: "Data structures and algorithms",
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(`skill=${navigation.skill}`),
}));

const api = vi.hoisted(() => ({
  getRoleRoadmap: vi.fn(),
  getSkillLibrary: vi.fn(),
}));

vi.mock("../api/career-growth-api", () => api);

const dsaLibrary = {
  disclaimer:
    "These are third-party learning resources. Rezumi does not host the courses.",
  howToStart: "Pick one structure a week.",
  library: {
    freeCourses: [
      {
        kind: "youtube",
        provider: "YouTube / freeCodeCamp",
        title: "Algorithms and Data Structures Tutorial — Full Course",
        url: "https://www.youtube.com/watch?v=8hly31xKli0",
      },
      {
        kind: "lecture_notes",
        provider: "Harvard CS50",
        title: "Harvard CS50 notes",
        url: "https://cs50.harvard.edu/x/notes/",
      },
    ],
    notes: [
      {
        content:
          "Data structures and algorithms\n\nCore ideas\nA hash map makes lookup cheap when you can pay for memory.",
        fileName: "data-structures-and-algorithms-concepts.pdf",
        format: "article",
        title: "Data structures and algorithms: what you actually need to know",
      },
    ],
    paidCourses: [
      {
        kind: "coursera",
        provider: "Coursera / Stanford",
        title: "Algorithms Specialization",
        url: "https://www.coursera.org/specializations/algorithms",
      },
      {
        kind: "udemy",
        provider: "Udemy",
        title: "Data Structures and Algorithms on Udemy",
        url: "https://www.udemy.com/courses/search/?src=ukw&q=data+structures+and+algorithms",
      },
    ],
  },
  skillName: "Data structures and algorithms",
  why: "Most engineering interviews assume fluency with core data structures.",
};

describe("Skill library panel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    navigation.skill = "Data structures and algorithms";
    api.getRoleRoadmap.mockResolvedValue({
      roleTitle: "Software Engineer",
      stages: [
        {
          skills: [
            {
              alreadyDemonstrated: false,
              howToStart: dsaLibrary.howToStart,
              library: dsaLibrary.library,
              name: dsaLibrary.skillName,
              why: dsaLibrary.why,
            },
          ],
          stage: "Foundations",
        },
      ],
    });
    api.getSkillLibrary.mockResolvedValue(dsaLibrary);
  });

  it("organizes notes, free courses, and paid courses for the mapped skill", async () => {
    render(
      <InterviewPrepWorkspaceMetricsProvider>
        <SkillLibraryPanel />
      </InterviewPrepWorkspaceMetricsProvider>,
    );

    expect(
      await screen.findByRole("heading", { name: "Skill library" }),
    ).toBeVisible();
    expect(
      await screen.findByRole("heading", {
        name: "Data structures and algorithms",
      }),
    ).toBeVisible();
    expect(screen.getByText("Foundations")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Data structures and algorithms" }),
    ).toHaveAttribute(
      "href",
      "/interview-prep/library?skill=Data%20structures%20and%20algorithms",
    );
    expect(
      screen.getByRole("tab", { name: "Study notes (1)" }),
    ).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText(/hash map makes lookup cheap/i)).toBeVisible();
    expect(screen.getByRole("button", { name: "Download PDF" })).toBeVisible();
    expect(screen.getByText(/does not host the courses/i)).toBeVisible();

    fireEvent.click(screen.getByRole("tab", { name: "Free courses (2)" }));
    expect(screen.getByText("Courses and videos")).toBeVisible();
    expect(screen.getByText("Docs and lecture notes")).toBeVisible();
    expect(screen.getByText("YouTube / freeCodeCamp")).toBeVisible();
    expect(screen.getByText("Harvard CS50")).toBeVisible();
    expect(
      screen.getByRole("link", {
        name: /Algorithms and Data Structures Tutorial/,
      }),
    ).toHaveAttribute("href", "https://www.youtube.com/watch?v=8hly31xKli0");
    expect(
      screen.getByRole("link", { name: /Harvard CS50 notes/ }),
    ).toHaveAttribute("href", "https://cs50.harvard.edu/x/notes/");

    fireEvent.click(screen.getByRole("tab", { name: "Paid courses (2)" }));
    expect(screen.getByText("Coursera / Stanford")).toBeVisible();
    expect(screen.getByText("Udemy")).toBeVisible();
    expect(
      screen.getByRole("link", { name: /Algorithms Specialization/ }),
    ).toHaveAttribute(
      "href",
      "https://www.coursera.org/specializations/algorithms",
    );
    expect(
      screen.getByRole("link", {
        name: /Data Structures and Algorithms on Udemy/,
      }),
    ).toHaveAttribute(
      "href",
      "https://www.udemy.com/courses/search/?src=ukw&q=data+structures+and+algorithms",
    );
  });
});
