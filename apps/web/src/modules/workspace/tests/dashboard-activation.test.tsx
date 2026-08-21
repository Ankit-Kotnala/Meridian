import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  ActivationChain,
  activationChain,
} from "../components/dashboard-activation";
import type { DashboardResumeHealth } from "../components/dashboard-resume-state";
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
    pipeline: unavailable,
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

const report: DashboardResumeHealth = {
  analysisId: "00000000-0000-4000-8000-000000000030",
  disclaimer: "Internal measure.",
  documentId: "00000000-0000-4000-8000-000000000031",
  filename: "fictional.pdf",
  kind: "report",
  score: 71,
  scoreBand: "developing",
  snapshotId: "00000000-0000-4000-8000-000000000032",
};

function stateOf(steps: readonly { id: string; state: string }[], id: string) {
  return steps.find((step) => step.id === id)?.state;
}

describe("activation chain projection", () => {
  it("marks only the first incomplete step as current", () => {
    const steps = activationChain(
      { documentId: "doc-1", filename: "fictional.pdf", kind: "review" },
      summary(),
    );

    expect(stateOf(steps, "resume")).toBe("done");
    expect(stateOf(steps, "review")).toBe("current");
    expect(stateOf(steps, "report")).toBe("pending");
    expect(stateOf(steps, "record")).toBe("pending");
    expect(stateOf(steps, "opportunity")).toBe("pending");
  });

  it("marks review and report complete once semantics are reviewed", () => {
    const steps = activationChain(
      {
        documentId: "doc-1",
        filename: "fictional.pdf",
        kind: "importReady",
        snapshotId: "00000000-0000-4000-8000-000000000032",
      },
      summary(),
    );

    expect(stateOf(steps, "review")).toBe("done");
    expect(stateOf(steps, "report")).toBe("done");
    expect(stateOf(steps, "record")).toBe("current");
  });

  it("points the review step at the document awaiting confirmation", () => {
    const steps = activationChain(
      { documentId: "doc 1/2", filename: "fictional.pdf", kind: "review" },
      summary(),
    );

    expect(steps.find((step) => step.id === "review")?.action).toEqual({
      href: "/resume-health/account/review/doc%201%2F2",
      label: "Review fields",
    });
  });

  it("routes the record step to the pending import decision", () => {
    const steps = activationChain(
      report,
      summary({
        activation: { jobs: count(0), pendingImports: count(4) },
        record: {
          achievements: count(0),
          evidence: count(0),
          evidenceConfirmed: count(0),
          experiences: count(0),
          skills: count(0),
        },
      }),
    );

    expect(stateOf(steps, "review")).toBe("done");
    expect(stateOf(steps, "report")).toBe("done");
    expect(stateOf(steps, "record")).toBe("current");
    expect(steps.find((step) => step.id === "record")?.action).toEqual({
      href: "/career-profile/imports",
      label: "Accept facts",
    });
  });

  it("completes every step once a record and an opportunity exist", () => {
    const steps = activationChain(
      report,
      summary({
        activation: { jobs: count(2), pendingImports: count(0) },
        record: {
          achievements: count(0),
          evidence: count(3),
          evidenceConfirmed: count(3),
          experiences: count(4),
          skills: count(9),
        },
      }),
    );

    expect(steps.every((step) => step.state === "done")).toBe(true);
  });

  it("keeps review complete once a report exists but the career record is empty", () => {
    const steps = activationChain(report, summary());

    expect(stateOf(steps, "review")).toBe("done");
    expect(stateOf(steps, "report")).toBe("done");
    expect(stateOf(steps, "record")).toBe("current");
  });

  it("reports an unknown step instead of claiming it is incomplete", () => {
    const steps = activationChain(
      report,
      summary({
        activation: { jobs: unavailable, pendingImports: unavailable },
        record: {
          achievements: count(0),
          evidence: count(0),
          evidenceConfirmed: count(0),
          experiences: unavailable,
          skills: count(0),
        },
      }),
    );

    expect(stateOf(steps, "record")).toBe("unknown");
    expect(stateOf(steps, "opportunity")).toBe("unknown");
  });

  it("offers recovery on the review step when processing failed", () => {
    const steps = activationChain(
      { filename: "fictional.pdf", kind: "failed" },
      summary(),
    );

    expect(steps.find((step) => step.id === "review")?.action).toEqual({
      href: "/resume-health/account",
      label: "Resolve",
    });
  });
});

describe("activation chain rendering", () => {
  it("summarizes progress and surfaces the current action", () => {
    render(
      <ActivationChain
        steps={activationChain(
          report,
          summary({
            activation: { jobs: count(0), pendingImports: count(2) },
            record: {
              achievements: count(0),
              evidence: count(0),
              evidenceConfirmed: count(0),
              experiences: count(0),
              skills: count(0),
            },
          }),
        )}
      />,
    );

    const region = screen.getByRole("region", {
      name: /steps complete/,
    });
    expect(
      within(region).getByRole("heading", { name: "3 of 5 steps complete" }),
    ).toBeVisible();
    expect(
      within(region).getByRole("link", { name: /Accept facts/ }),
    ).toHaveAttribute("href", "/career-profile/imports");
  });

  it("warns when a step state could not be loaded", () => {
    render(
      <ActivationChain
        steps={activationChain(
          report,
          summary({
            record: {
              achievements: count(0),
              evidence: count(0),
              evidenceConfirmed: count(0),
              experiences: unavailable,
              skills: count(0),
            },
          }),
        )}
      />,
    );

    expect(
      screen.getByText("Some step states could not be loaded"),
    ).toBeVisible();
    expect(screen.getAllByText("Status unavailable").length).toBeGreaterThan(0);
  });
});
