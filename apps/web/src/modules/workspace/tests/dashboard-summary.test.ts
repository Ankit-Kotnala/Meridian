import { beforeEach, describe, expect, it, vi } from "vitest";

const { serverApiFetch } = vi.hoisted(() => ({ serverApiFetch: vi.fn() }));

vi.mock("@/shared/api/server-request", () => ({ serverApiFetch }));

const { dashboardSummary } = await import("../server/dashboard-summary");

function json(payload: unknown) {
  return { json: async () => payload, ok: true };
}

function inDays(days: number): string {
  return new Date(Date.now() + days * 86_400_000).toISOString().slice(0, 10);
}

const page = { hasMore: false, limit: 100, nextCursor: null };

type Payloads = Partial<Record<string, unknown>>;

function respondWith(payloads: Payloads, failing: readonly string[] = []) {
  serverApiFetch.mockImplementation(async (path: string) => {
    const key = Object.keys(payloads).find((candidate) =>
      path.startsWith(candidate),
    );
    if (failing.some((candidate) => path.startsWith(candidate))) {
      return { json: async () => ({}), ok: false };
    }
    return json(key ? payloads[key] : { data: [], page });
  });
}

describe("dashboard summary", () => {
  beforeEach(() => {
    serverApiFetch.mockReset();
  });

  it("aggregates the account's own record without inventing totals", async () => {
    respondWith({
      "/api/v1/achievements": {
        data: [
          { status: "draft" },
          { status: "ready" },
          { status: "converted" },
        ],
        page,
      },
      "/api/v1/applications": {
        data: [
          { openTaskCount: 2, stage: "saved" },
          { openTaskCount: 0, stage: "interview" },
          { openTaskCount: 0, stage: "rejected" },
        ],
        page,
      },
      "/api/v1/evidence": {
        data: [{ state: "confirmed" }, { state: "inferred" }],
        page,
      },
      "/api/v1/experiences": { data: [{ id: "a" }, { id: "b" }], findings: [] },
      "/api/v1/skills": {
        data: [{ userConfirmed: true }, { userConfirmed: false }],
      },
    });

    const summary = await dashboardSummary();

    expect(summary.record.experiences).toEqual({
      atLeast: false,
      kind: "count",
      value: 2,
    });
    expect(summary.record.evidence).toEqual({
      atLeast: false,
      kind: "count",
      value: 2,
    });
    expect(summary.record.achievements).toEqual({
      atLeast: false,
      kind: "count",
      value: 2,
    });
    expect(summary.pipeline).toMatchObject({
      kind: "ready",
      openTasks: 2,
      total: 3,
    });
    if (summary.pipeline.kind !== "ready") throw new Error("unreachable");
    expect(
      summary.pipeline.groups.map(({ count, key }) => [key, count]),
    ).toEqual([
      ["exploring", 1],
      ["applied", 0],
      ["interviewing", 1],
      ["offer", 0],
      ["closed", 1],
    ]);
    expect(summary.attentionDegraded).toBe(false);
  });

  it("marks a full cursor page as an at-least count", async () => {
    respondWith({
      "/api/v1/evidence": {
        data: Array.from({ length: 100 }, () => ({ state: "confirmed" })),
        page: { hasMore: true, limit: 100, nextCursor: "next" },
      },
    });

    const summary = await dashboardSummary();

    expect(summary.record.evidence).toEqual({
      atLeast: true,
      kind: "count",
      value: 100,
    });
  });

  it("reports an unavailable section instead of a zero when a source fails", async () => {
    respondWith({ "/api/v1/skills": { data: [{ userConfirmed: true }] } }, [
      "/api/v1/experiences",
      "/api/v1/applications",
    ]);

    const summary = await dashboardSummary();

    expect(summary.record.experiences).toEqual({ kind: "unavailable" });
    expect(summary.pipeline).toEqual({ kind: "unavailable" });
    expect(summary.record.skills).toEqual({
      atLeast: false,
      kind: "count",
      value: 1,
    });
    expect(summary.attentionDegraded).toBe(true);
  });

  it("derives review items from real deadlines, evidence, and drafts", async () => {
    respondWith({
      "/api/v1/achievements": { data: [{ status: "draft" }], page },
      "/api/v1/applications": {
        data: [
          {
            applicationDeadline: inDays(3),
            followUpAt: "2020-01-01",
            openTaskCount: 0,
            stage: "preparing",
          },
        ],
        page,
      },
      "/api/v1/evidence": { data: [{ state: "unsupported" }], page },
      "/api/v1/experiences": {
        data: [],
        findings: [{ id: "conflict" }],
      },
    });

    const summary = await dashboardSummary();
    const ids = summary.attention.map(({ id }) => id);

    expect(ids).toContain("profile-conflicts");
    expect(ids).toContain("application-deadlines");
    expect(ids).toContain("application-follow-ups");
    expect(ids).toContain("evidence-confirmation");
    expect(ids).toContain("achievement-drafts");
    expect(ids).not.toContain("application-tasks");
    expect(summary.attention[0]).toMatchObject({
      href: "/career-profile",
      tone: "danger",
    });
  });

  it("ignores deadlines on closed applications", async () => {
    respondWith({
      "/api/v1/applications": {
        data: [
          {
            applicationDeadline: inDays(2),
            openTaskCount: 0,
            stage: "withdrawn",
          },
        ],
        page,
      },
    });

    const summary = await dashboardSummary();

    expect(summary.attention.map(({ id }) => id)).not.toContain(
      "application-deadlines",
    );
  });
});
