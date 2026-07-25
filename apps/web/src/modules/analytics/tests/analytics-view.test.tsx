import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  AnalyticsRefresh,
  AnalyticsReport,
  AnalyticsScope,
} from "../api/types";
import {
  AnalyticsView,
  NON_CAUSAL_INTERPRETATION,
  calendarDateInTimezone,
  defaultAnalyticsWindow,
} from "../views/analytics-view";

const api = vi.hoisted(() => ({
  getAnalyticsRefresh: vi.fn(),
  getAnalyticsReport: vi.fn(),
  requestAnalyticsRefresh: vi.fn(),
}));

vi.mock("../api/analytics-api", () => api);

const refresh = {
  attempts: 0,
  completedAt: null,
  createdAt: "2026-07-24T12:00:00Z",
  id: "00000000-0000-4000-8000-000000009101",
  maxAttempts: 3,
  safeErrorCode: null,
  scope: "overview",
  status: "queued",
  timezone: "Asia/Kolkata",
  updatedAt: "2026-07-24T12:00:00Z",
  version: 1,
  windowEnd: "2026-07-24",
  windowStart: "2025-07-24",
} satisfies AnalyticsRefresh;

function refreshFor(
  input: {
    scope: AnalyticsScope;
    timezone: string;
    windowEnd: string;
    windowStart: string;
  },
  overrides: Partial<AnalyticsRefresh> = {},
): AnalyticsRefresh {
  return {
    ...refresh,
    scope: input.scope,
    timezone: input.timezone,
    windowEnd: input.windowEnd,
    windowStart: input.windowStart,
    ...overrides,
  };
}

function report(
  scope: AnalyticsScope = "overview",
  overrides: Partial<AnalyticsReport> = {},
): AnalyticsReport {
  return {
    freshness: "current",
    generatedAt: "2026-07-24T12:05:00Z",
    interpretation:
      "Observed activity in this private workspace during the selected window.",
    metricDefinitionVersion: "career-analytics/1",
    timezone: "Asia/Kolkata",
    cohortDefinition:
      "Applications whose local first-applied date is inside the selected window.",
    metricDefinitions: [
      {
        cohort: "Selected applications.",
        denominator: "All selected applications.",
        description: "Observed interview events.",
        eventTimestamp: "firstInterviewAt",
        key: "interviewRate",
        numerator: "Applications with an interview event.",
        suppressionMinimum: 5,
        version: "career-analytics/1",
      },
    ],
    suppressionPolicy: {
      appliesTo: "Every rate and average.",
      minimumDenominator: 5,
      reason: "Small cohorts are hidden.",
      suppressedFields: "Values and sample sizes are null.",
    },
    timestampSemantics: {
      applicationCohort: "Uses firstAppliedAt in the report timezone.",
    },
    payload: {
      breakdowns: {
        application_stage: [
          { count: 8, key: "interviewing" },
          { count: 3, key: "other" },
        ],
      },
      counts: {
        achievements: 6,
        applications: 11,
        interviews: 4,
      },
      interpretation:
        "Observed activity in this private workspace during the selected window.",
      metricDefinitionVersion: "career-analytics/1",
      outcomesByResumeVersion: [
        {
          applicationCount: 4,
          interviewRate: {
            denominator: null,
            numerator: null,
            suppressed: true,
            suppressionReason: "Small cohorts are hidden.",
            valueBasisPoints: null,
          },
          offerRate: {
            denominator: null,
            numerator: null,
            suppressed: true,
            suppressionReason: "Small cohorts are hidden.",
            valueBasisPoints: null,
          },
          responseRate: {
            denominator: null,
            numerator: null,
            suppressed: true,
            suppressionReason: "Small cohorts are hidden.",
            valueBasisPoints: null,
          },
          resumeVersionId: "00000000-0000-4000-8000-000000009103",
          resumeVersionNumber: 3,
        },
      ],
      rates: {
        interview_rate: {
          denominator: 4,
          numerator: 2,
          suppressed: true,
          suppressionReason: "Fewer than 5 eligible observations.",
          valueBasisPoints: null,
        },
        response_rate: {
          denominator: 11,
          numerator: 6,
          suppressed: false,
          suppressionReason: null,
          valueBasisPoints: 5455,
        },
      },
      requirementCoverageTrend: [
        {
          end: "2026-07-15",
          sampleSize: null,
          start: "2026-07-01",
          suppressed: true,
          suppressionReason: "Small cohorts are hidden.",
          valueBasisPoints: null,
        },
      ],
      readinessHistory: [
        {
          analysisId: "00000000-0000-4000-8000-000000009102",
          createdAt: "2026-07-20T12:00:00Z",
          engineVersion: "role-readiness/1",
          label: "developing",
          rawScoreBasisPoints: 7200,
          roleLabel: "Principal Engineer",
        },
      ],
      scope,
      timeBuckets: [
        {
          achievements: 2,
          applications: 5,
          end: "2026-07-15",
          interviews: 2,
          offers: 0,
          start: "2026-07-01",
        },
      ],
    },
    refresh: null,
    scope,
    sourceWatermarks: {
      applications: {
        maxUpdatedAt: "2026-07-24T12:00:00Z",
        recordCount: 11,
        source: "applications",
        token: `sha256:${"a".repeat(64)}`,
      },
    },
    status: "ready",
    windowEnd: "2026-07-24",
    windowStart: "2025-07-24",
    ...overrides,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

describe("Career Analytics view", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getAnalyticsReport.mockResolvedValue(report());
    let accepted: AnalyticsRefresh = refresh;
    api.requestAnalyticsRefresh.mockImplementation(
      async (input: Parameters<typeof refreshFor>[0]) => {
        accepted = refreshFor(input);
        return accepted;
      },
    );
    api.getAnalyticsRefresh.mockImplementation(async () => ({
      ...accepted,
      completedAt: "2026-07-24T12:06:00Z",
      status: "completed",
      version: 2,
    }));
  });

  it("derives calendar defaults in the resolved IANA timezone", () => {
    expect(
      calendarDateInTimezone(
        new Date("2026-01-01T00:30:00.000Z"),
        "America/Los_Angeles",
      ),
    ).toBe("2025-12-31");
    expect(
      calendarDateInTimezone(
        new Date("2025-12-31T10:30:00.000Z"),
        "Pacific/Kiritimati",
      ),
    ).toBe("2026-01-01");
    expect(
      defaultAnalyticsWindow(new Date("2024-02-29T12:00:00.000Z"), "UTC"),
    ).toEqual({
      scope: "overview",
      timezone: "UTC",
      windowEnd: "2024-02-29",
      windowStart: "2023-02-28",
    });
  });

  it("renders table-first summaries, permanent interpretation limits, and privacy suppression", async () => {
    render(<AnalyticsView />);

    expect(
      await screen.findByRole("heading", { name: "Overview report" }),
    ).toBeVisible();
    expect(api.getAnalyticsReport).toHaveBeenCalledWith(
      expect.objectContaining({ timezone: expect.any(String) }),
      expect.any(AbortSignal),
    );
    expect(screen.getAllByText(NON_CAUSAL_INTERPRETATION)).toHaveLength(2);
    expect(
      screen.getByRole("table", {
        name: /Observed rates; small cohorts are suppressed/i,
      }),
    ).toBeVisible();
    expect(
      screen.getAllByText("Suppressed (<5 observations)")[0],
    ).toBeVisible();
    expect(screen.queryByText("2 of 4")).not.toBeInTheDocument();
    expect(screen.getByText("Other categories")).toBeVisible();
    expect(
      screen.getByRole("table", {
        name: /Applications, interviews, offers, and achievements/i,
      }),
    ).toBeVisible();
    expect(screen.getByText("Principal Engineer")).toBeVisible();
    expect(
      screen.getByRole("table", {
        name: /Requirement coverage trend; small samples are suppressed/i,
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("table", {
        name: /Observed outcomes segmented by exact immutable resume version/i,
      }),
    ).toBeVisible();
    expect(
      screen.getByText("Metric, cohort, and timestamp definitions"),
    ).toBeVisible();
    expect(screen.getByText(/Calendar timezone: Asia\/Kolkata/i)).toBeVisible();
    expect(
      screen.getByText("Source completeness watermarks (1)"),
    ).toBeVisible();

    expect(screen.queryByText("private resume body")).not.toBeInTheDocument();
    expect(screen.queryByText("person@example.com")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /send/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /apply for/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/this caused/i)).not.toBeInTheDocument();
  });

  it("renders loading, empty, and retryable failure states", async () => {
    const pending = deferred<AnalyticsReport>();
    api.getAnalyticsReport.mockReturnValueOnce(pending.promise);
    const first = render(<AnalyticsView />);
    expect(screen.getByText("Loading content")).toBeInTheDocument();

    await act(async () => {
      pending.resolve(
        report("overview", {
          freshness: "empty",
          generatedAt: null,
          payload: null,
          status: null,
        }),
      );
    });
    expect(
      await screen.findByRole("heading", { name: "No analytics snapshot yet" }),
    ).toBeVisible();
    first.unmount();

    api.getAnalyticsReport.mockRejectedValueOnce(new Error("offline"));
    render(<AnalyticsView />);
    expect(
      await screen.findByRole("heading", {
        name: "Career Analytics unavailable",
      }),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Try again" })).toBeVisible();
  });

  it("aborts a superseded report and ignores its late result", async () => {
    const oldReport = deferred<AnalyticsReport>();
    const newReport = deferred<AnalyticsReport>();
    const signals: AbortSignal[] = [];
    api.getAnalyticsReport
      .mockImplementationOnce(
        (_filters: unknown, signal?: AbortSignal): Promise<AnalyticsReport> => {
          if (signal) signals.push(signal);
          return oldReport.promise;
        },
      )
      .mockImplementationOnce(
        (_filters: unknown, signal?: AbortSignal): Promise<AnalyticsReport> => {
          if (signal) signals.push(signal);
          return newReport.promise;
        },
      );

    render(<AnalyticsView />);
    await waitFor(() => expect(signals).toHaveLength(1));
    fireEvent.change(screen.getByLabelText("View"), {
      target: { value: "applications" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply window" }));

    await waitFor(() => expect(signals).toHaveLength(2));
    expect(signals[0]?.aborted).toBe(true);
    await act(async () => {
      newReport.resolve(report("applications"));
    });
    expect(
      await screen.findByRole("heading", { name: "Applications report" }),
    ).toBeVisible();

    await act(async () => {
      oldReport.resolve(report("overview"));
    });
    expect(
      screen.queryByRole("heading", { name: "Overview report" }),
    ).not.toBeInTheDocument();
  });

  it("reuses one idempotency key when the same refresh intent is retried", async () => {
    api.requestAnalyticsRefresh
      .mockRejectedValueOnce(new Error("offline"))
      .mockImplementationOnce(async (input: Parameters<typeof refreshFor>[0]) =>
        refreshFor(input),
      );
    render(<AnalyticsView />);
    await screen.findByRole("heading", { name: "Overview report" });
    const button = screen.getByRole("button", { name: "Refresh report" });

    fireEvent.click(button);
    await waitFor(() =>
      expect(api.requestAnalyticsRefresh).toHaveBeenCalledTimes(1),
    );
    expect(
      await screen.findByText(/refresh could not be queued/i),
    ).toBeVisible();
    fireEvent.click(button);
    await waitFor(() =>
      expect(api.requestAnalyticsRefresh).toHaveBeenCalledTimes(2),
    );

    const firstKey = api.requestAnalyticsRefresh.mock.calls[0]?.[1];
    const secondKey = api.requestAnalyticsRefresh.mock.calls[1]?.[1];
    expect(firstKey).toEqual(secondKey);
    expect(firstKey).toMatch(/^analytics\.overview\./);
  });

  it("deduplicates overlapping refresh clicks for the same filter intent", async () => {
    const pending = deferred<AnalyticsRefresh>();
    api.requestAnalyticsRefresh.mockReturnValueOnce(pending.promise);
    render(<AnalyticsView />);
    await screen.findByRole("heading", { name: "Overview report" });
    const button = screen.getByRole("button", { name: "Refresh report" });

    fireEvent.click(button);
    fireEvent.click(button);

    expect(api.requestAnalyticsRefresh).toHaveBeenCalledTimes(1);
    const input = api.requestAnalyticsRefresh.mock.calls[0]?.[0];
    await act(async () => {
      pending.resolve(refreshFor(input));
    });
    expect(await screen.findByText(/refresh queued/i)).toBeVisible();
  });

  it("does not attach a late refresh response to a new filter epoch", async () => {
    const pending = deferred<AnalyticsRefresh>();
    api.requestAnalyticsRefresh.mockReturnValueOnce(pending.promise);
    render(<AnalyticsView />);
    await screen.findByRole("heading", { name: "Overview report" });

    fireEvent.click(screen.getByRole("button", { name: "Refresh report" }));
    const originalInput = api.requestAnalyticsRefresh.mock.calls[0]?.[0];
    fireEvent.change(screen.getByLabelText("View"), {
      target: { value: "applications" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply window" }));
    await screen.findByRole("heading", { name: "Overview report" });

    await act(async () => {
      pending.resolve(refreshFor(originalInput));
    });

    expect(screen.queryByText(/refresh queued/i)).not.toBeInTheDocument();
    expect(api.getAnalyticsRefresh).not.toHaveBeenCalled();
  });

  it("ignores a late poll from filter A instead of reloading filter B", async () => {
    const pendingPoll = deferred<AnalyticsRefresh>();
    api.getAnalyticsRefresh.mockReturnValueOnce(pendingPoll.promise);
    render(<AnalyticsView />);
    await screen.findByRole("heading", { name: "Overview report" });

    fireEvent.click(screen.getByRole("button", { name: "Refresh report" }));
    await waitFor(
      () => expect(api.getAnalyticsRefresh).toHaveBeenCalledTimes(1),
      { timeout: 2500 },
    );
    const originalInput = api.requestAnalyticsRefresh.mock.calls[0]?.[0];
    fireEvent.change(screen.getByLabelText("View"), {
      target: { value: "applications" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply window" }));
    await waitFor(() =>
      expect(api.getAnalyticsReport).toHaveBeenCalledTimes(2),
    );

    await act(async () => {
      pendingPoll.resolve(
        refreshFor(originalInput, {
          completedAt: "2026-07-24T12:06:00Z",
          status: "completed",
          version: 2,
        }),
      );
    });

    expect(
      screen.queryByText("Analytics refresh completed."),
    ).not.toBeInTheDocument();
    expect(api.getAnalyticsReport).toHaveBeenCalledTimes(2);
  });

  it("polls an accepted refresh and authoritatively reloads the completed report", async () => {
    render(<AnalyticsView />);
    await screen.findByRole("heading", { name: "Overview report" });

    fireEvent.click(screen.getByRole("button", { name: "Refresh report" }));
    expect(await screen.findByText(/refresh queued/i)).toBeVisible();

    await waitFor(
      () =>
        expect(api.getAnalyticsRefresh).toHaveBeenCalledWith(
          refresh.id,
          expect.any(AbortSignal),
        ),
      { timeout: 2500 },
    );
    await waitFor(() =>
      expect(api.getAnalyticsReport).toHaveBeenCalledTimes(2),
    );
    expect(
      await screen.findByText("Analytics refresh completed."),
    ).toBeVisible();
  });
});
