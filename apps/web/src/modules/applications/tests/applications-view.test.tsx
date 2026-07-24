import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Application, ApplicationDetail } from "../api/types";
import { ApplicationsView } from "../views/applications-view";

const navigation = vi.hoisted(() => ({
  params: new URLSearchParams(),
  replace: vi.fn(),
}));

const api = vi.hoisted(() => ({
  getApplicationCalendar: vi.fn(),
  listApplications: vi.fn(),
  updateApplicationStage: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/applications",
  useRouter: () => ({ replace: navigation.replace }),
  useSearchParams: () => navigation.params,
}));

vi.mock("../api/applications-api", () => ({
  ApiRequestError: class extends Error {
    failure = { status: 409 };
  },
  ...api,
}));

vi.mock("../components/create-application-form", () => ({
  CreateApplicationForm: ({
    onCreated,
  }: {
    onCreated: (application: ApplicationDetail) => void;
  }) => (
    <button onClick={() => onCreated(detail)} type="button">
      Complete application creation
    </button>
  ),
}));

const application: Application = {
  applicationDeadline: "2026-08-01",
  company: "Example Co",
  createdAt: "2026-07-20T12:00:00Z",
  eventCount: 2,
  followUpAt: "2026-07-27",
  id: "00000000-0000-4000-8000-000000008001",
  industry: "Software",
  jobAnalysisId: null,
  jobId: "00000000-0000-4000-8000-000000008002",
  jobTitle: "Product Engineer",
  jobVersion: 2,
  location: "Remote",
  noteCount: 1,
  offerSummary: null,
  openTaskCount: 1,
  outcomeStatus: "none",
  packCount: 0,
  referralStatus: "requested",
  rejectionReason: null,
  resumeId: "00000000-0000-4000-8000-000000008003",
  resumeTitle: "Product resume",
  resumeVersionId: "00000000-0000-4000-8000-000000008004",
  resumeVersionNumber: 4,
  source: "Referral",
  stage: "preparing",
  taskCount: 2,
  updatedAt: "2026-07-24T12:00:00Z",
  version: 3,
};

const detail = {
  ...application,
  contacts: [],
  evidencePins: [],
  jobRequirements: [],
  jobSourceSha256: "a".repeat(64),
  resumeClaims: [],
  resumeEvidenceIds: [],
} satisfies ApplicationDetail;

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

function calendar(month: string, title: string) {
  return {
    data: [
      {
        applicationId: application.id,
        completed: false,
        id: `00000000-0000-4000-8000-${month.replace("-", "")}0001`,
        kind: "task" as const,
        onDate: `${month}-15`,
        title,
      },
    ],
    end: `${month}-28`,
    start: `${month}-01`,
  };
}

describe("Application Workspace list", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    navigation.params = new URLSearchParams();
    api.listApplications.mockResolvedValue({
      data: [application],
      page: { hasMore: false, limit: 100, nextCursor: null },
    });
    api.updateApplicationStage.mockResolvedValue({
      ...detail,
      stage: "ready_to_apply",
      version: 4,
    });
  });

  it("renders the board and provides a non-drag stage control", async () => {
    render(<ApplicationsView />);

    expect(
      await screen.findByRole("heading", { name: "Product Engineer" }),
    ).toBeVisible();
    expect(
      screen.getByText(/CareerOS never submits an application on your behalf/i),
    ).toBeVisible();

    fireEvent.change(
      screen.getByRole("combobox", {
        name: "Move Product Engineer to stage",
      }),
      { target: { value: "ready_to_apply" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Move" }));

    expect(api.updateApplicationStage).toHaveBeenCalledWith(application, {
      stage: "ready_to_apply",
    });
    expect(await screen.findByRole("status")).toHaveTextContent(
      /moved to Ready To Apply/i,
    );
    expect(
      screen.getAllByText(/Product Engineer moved to Ready To Apply/i),
    ).toHaveLength(1);
  });

  it("writes search, source, and view choices to the URL", async () => {
    render(<ApplicationsView />);
    await screen.findByRole("heading", { name: "Product Engineer" });

    fireEvent.change(screen.getByLabelText("Search applications"), {
      target: { value: "engineer" },
    });
    fireEvent.change(screen.getByLabelText("Source"), {
      target: { value: "referral" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(navigation.replace).toHaveBeenCalledWith(
      expect.stringContaining("q=engineer"),
      { scroll: false },
    );
    expect(navigation.replace).toHaveBeenCalledWith(
      expect.stringContaining("source=referral"),
      { scroll: false },
    );

    fireEvent.click(screen.getByRole("button", { name: "Table" }));
    expect(navigation.replace).toHaveBeenCalledWith(
      "/applications?view=table",
      { scroll: false },
    );
  });

  it("collapses the creation panel after an application is added", async () => {
    render(<ApplicationsView />);
    await screen.findByRole("heading", { name: "Product Engineer" });

    const summary = screen.getByText("Add an application", { exact: true });
    fireEvent.click(summary);
    const details = summary.closest("details");
    if (!details) throw new Error("Application details control was not found.");
    expect(details).toHaveAttribute("open");
    fireEvent(details, new Event("toggle"));
    fireEvent.click(
      await screen.findByRole("button", {
        name: "Complete application creation",
      }),
    );

    await waitFor(() =>
      expect(
        screen
          .getByText("Add an application", { exact: true })
          .closest("details"),
      ).not.toHaveAttribute("open"),
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Product Engineer added to your workspace.",
    );
  });

  it("renders a retryable initial failure", async () => {
    api.listApplications.mockRejectedValue(new Error("offline"));
    render(<ApplicationsView />);

    expect(
      await screen.findByRole("heading", {
        name: "Application Workspace unavailable",
      }),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Try again" })).toBeVisible();
  });

  it("clears old results and ignores late filter responses", async () => {
    const stale = deferred<{
      data: Application[];
      page: { hasMore: boolean; limit: number; nextCursor: string | null };
    }>();
    const latest = deferred<{
      data: Application[];
      page: { hasMore: boolean; limit: number; nextCursor: string | null };
    }>();
    api.listApplications
      .mockResolvedValueOnce({
        data: [application],
        page: { hasMore: true, limit: 100, nextCursor: "old-cursor" },
      })
      .mockReturnValueOnce(stale.promise)
      .mockReturnValueOnce(latest.promise);
    const { rerender } = render(<ApplicationsView />);

    expect(
      await screen.findByRole("heading", { name: "Product Engineer" }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Load more applications" }),
    ).toBeVisible();

    navigation.params = new URLSearchParams("q=first");
    rerender(<ApplicationsView />);
    await waitFor(() => expect(api.listApplications).toHaveBeenCalledTimes(2));
    expect(
      screen.queryByRole("heading", { name: "Product Engineer" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Load more applications" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Loading content")).toBeInTheDocument();

    navigation.params = new URLSearchParams("q=latest");
    rerender(<ApplicationsView />);
    await waitFor(() => expect(api.listApplications).toHaveBeenCalledTimes(3));
    await act(async () => {
      latest.resolve({
        data: [
          {
            ...application,
            id: "00000000-0000-4000-8000-000000008031",
            jobTitle: "Latest role",
          },
        ],
        page: { hasMore: false, limit: 100, nextCursor: null },
      });
      await latest.promise;
    });
    expect(
      await screen.findByRole("heading", { name: "Latest role" }),
    ).toBeVisible();

    await act(async () => {
      stale.resolve({
        data: [
          {
            ...application,
            id: "00000000-0000-4000-8000-000000008032",
            jobTitle: "Stale role",
          },
        ],
        page: { hasMore: true, limit: 100, nextCursor: "stale-cursor" },
      });
      await stale.promise;
    });
    expect(screen.getByRole("heading", { name: "Latest role" })).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Stale role" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Load more applications" }),
    ).not.toBeInTheDocument();
  });

  it("does not append a late cursor page after filters change", async () => {
    const oldPage = deferred<{
      data: Application[];
      page: { hasMore: boolean; limit: number; nextCursor: string | null };
    }>();
    api.listApplications
      .mockResolvedValueOnce({
        data: [application],
        page: { hasMore: true, limit: 100, nextCursor: "next-old-page" },
      })
      .mockReturnValueOnce(oldPage.promise)
      .mockResolvedValueOnce({
        data: [
          {
            ...application,
            id: "00000000-0000-4000-8000-000000008041",
            jobTitle: "Filtered role",
          },
        ],
        page: { hasMore: false, limit: 100, nextCursor: null },
      });
    const { rerender } = render(<ApplicationsView />);

    await screen.findByRole("heading", { name: "Product Engineer" });
    fireEvent.click(
      screen.getByRole("button", { name: "Load more applications" }),
    );
    await waitFor(() => expect(api.listApplications).toHaveBeenCalledTimes(2));

    navigation.params = new URLSearchParams("q=filtered");
    rerender(<ApplicationsView />);
    expect(
      await screen.findByRole("heading", { name: "Filtered role" }),
    ).toBeVisible();

    await act(async () => {
      oldPage.resolve({
        data: [
          {
            ...application,
            id: "00000000-0000-4000-8000-000000008042",
            jobTitle: "Late old page",
          },
        ],
        page: { hasMore: false, limit: 100, nextCursor: null },
      });
      await oldPage.promise;
    });
    expect(
      screen.queryByRole("heading", { name: "Late old page" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Filtered role" }),
    ).toBeVisible();
  });

  it("does not retain old results or their cursor when a new query fails", async () => {
    api.listApplications
      .mockResolvedValueOnce({
        data: [application],
        page: { hasMore: true, limit: 100, nextCursor: "old-cursor" },
      })
      .mockRejectedValueOnce(new Error("offline"));
    const { rerender } = render(<ApplicationsView />);

    await screen.findByRole("heading", { name: "Product Engineer" });
    navigation.params = new URLSearchParams("q=unavailable");
    rerender(<ApplicationsView />);

    expect(
      await screen.findByRole("heading", {
        name: "Application Workspace unavailable",
      }),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Product Engineer" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Load more applications" }),
    ).not.toBeInTheDocument();
  });

  it("clears stale calendar content and ignores late rapid-navigation responses", async () => {
    const july = deferred<ReturnType<typeof calendar>>();
    const august = deferred<ReturnType<typeof calendar>>();
    const september = deferred<ReturnType<typeof calendar>>();
    api.getApplicationCalendar
      .mockReturnValueOnce(july.promise)
      .mockReturnValueOnce(august.promise)
      .mockReturnValueOnce(september.promise);
    navigation.params = new URLSearchParams("view=calendar&month=2026-07");
    const { rerender } = render(<ApplicationsView />);

    await waitFor(() =>
      expect(api.getApplicationCalendar).toHaveBeenCalledTimes(1),
    );
    await act(async () => {
      july.resolve(calendar("2026-07", "July follow-up"));
      await july.promise;
    });
    expect(await screen.findByText("July follow-up")).toBeVisible();

    navigation.params = new URLSearchParams("view=calendar&month=2026-08");
    rerender(<ApplicationsView />);
    await waitFor(() =>
      expect(api.getApplicationCalendar).toHaveBeenCalledTimes(2),
    );
    expect(screen.queryByText("July follow-up")).not.toBeInTheDocument();
    expect(screen.getByText("Loading content")).toBeInTheDocument();

    navigation.params = new URLSearchParams("view=calendar&month=2026-09");
    rerender(<ApplicationsView />);
    await waitFor(() =>
      expect(api.getApplicationCalendar).toHaveBeenCalledTimes(3),
    );
    await act(async () => {
      september.resolve(calendar("2026-09", "September interview"));
      await september.promise;
    });
    expect(await screen.findByText("September interview")).toBeVisible();

    await act(async () => {
      august.resolve(calendar("2026-08", "Stale August deadline"));
      await august.promise;
    });
    expect(screen.getByText("September interview")).toBeVisible();
    expect(screen.queryByText("Stale August deadline")).not.toBeInTheDocument();
  });

  it("shows an inline retry when the calendar request fails", async () => {
    navigation.params = new URLSearchParams("view=calendar&month=2026-07");
    api.getApplicationCalendar
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(calendar("2026-07", "Recovered deadline"));
    render(<ApplicationsView />);

    expect(
      await screen.findByRole("heading", { name: "Calendar unavailable" }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Recovered deadline")).toBeVisible();
  });
});
