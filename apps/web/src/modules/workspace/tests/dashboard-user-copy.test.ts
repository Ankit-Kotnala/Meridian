import { describe, expect, it } from "vitest";

import { heroSubtitle, recordStatsFootnote } from "../lib/dashboard-user-copy";
import type { DashboardSummary } from "../server/dashboard-summary";

const unavailable = { kind: "unavailable" } as const;

function count(value: number) {
  return { atLeast: false, kind: "count", value } as const;
}

function summary(overrides: Partial<DashboardSummary> = {}): DashboardSummary {
  return {
    activation: { jobs: count(0), pendingImports: count(0) },
    attention: [],
    attentionDegraded: false,
    growth: unavailable,
    jobHunt: unavailable,
    pipeline: unavailable,
    prepare: unavailable,
    record: {
      achievements: count(0),
      evidence: count(0),
      evidenceConfirmed: count(0),
      experiences: count(0),
      skills: count(0),
    },
    ...overrides,
  };
}

describe("dashboard user copy", () => {
  it("summarizes what the user has on their profile", () => {
    expect(
      heroSubtitle(
        summary({
          record: {
            achievements: count(1),
            evidence: count(3),
            evidenceConfirmed: count(2),
            experiences: count(2),
            skills: count(5),
          },
        }),
        { kind: "empty" },
      ),
    ).toContain("2 roles");
  });

  it("prioritizes attention items in the hero", () => {
    expect(
      heroSubtitle(
        summary({
          attention: [
            {
              description: "Due today",
              href: "/applications",
              id: "deadline",
              label: "Deadline",
              tone: "warning",
            },
          ],
        }),
        { kind: "empty" },
      ),
    ).toContain("1 item needs your review");
  });

  it("notes open achievements in the profile footnote", () => {
    expect(
      recordStatsFootnote({
        achievements: count(2),
        evidence: count(4),
        evidenceConfirmed: count(1),
        experiences: count(3),
        skills: count(6),
      }),
    ).toContain("2 achievements still open");
  });
});
