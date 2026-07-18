import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Experience } from "../api/types";
import { CareerTimeline } from "../components/experience-views";

const yearOnlyExperience: Experience = {
  concurrentGroupId: null,
  conflicts: [],
  createdAt: "2026-07-15T00:00:00Z",
  current: false,
  description: "",
  displayTitle: null,
  employer: "Fictional Co",
  employmentType: null,
  endDate: "2024",
  id: "00000000-0000-4000-8000-000000000601",
  location: null,
  officialTitle: "Engineer",
  order: 0,
  promotionGroupId: null,
  provenance: [],
  skillIds: [],
  startDate: "2020",
  updatedAt: "2026-07-15T00:00:00Z",
  userConfirmed: true,
  version: 1,
};

describe("partial-date rendering", () => {
  it("renders year-only career dates verbatim without inventing January", () => {
    render(<CareerTimeline experiences={[yearOnlyExperience]} />);

    expect(screen.getByText(/2020\s+–\s+2024/)).toBeVisible();
    expect(screen.queryByText(/Jan/)).not.toBeInTheDocument();
  });
});
