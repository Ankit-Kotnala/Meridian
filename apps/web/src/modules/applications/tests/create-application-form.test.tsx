import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  ApplicationDetail,
  SavedJob,
  SavedResume,
  SavedResumeVersion,
} from "../api/types";
import { CreateApplicationForm } from "../components/create-application-form";

const api = vi.hoisted(() => ({
  createApplication: vi.fn(),
  listApplicationSourceJobs: vi.fn(),
  listApplicationSourceResumes: vi.fn(),
  listApplicationSourceResumeVersions: vi.fn(),
}));

vi.mock("../api/applications-api", () => api);

const resumeVersion: SavedResumeVersion = {
  createdAt: "2026-07-24T12:00:00Z",
  entities: [],
  id: "00000000-0000-4000-8000-000000008204",
  layout: {
    fontFamily: "sans",
    fontSizePt: 10,
    lineSpacing: "standard",
    margins: "standard",
    pageLimit: 1,
    pageSize: "letter",
  },
  parentVersionId: null,
  personalFacts: [],
  plainText: "Product Engineer",
  resumeId: "00000000-0000-4000-8000-000000008203",
  sections: [],
  sourceChangeSetId: null,
  sourceChangeSetVersionId: null,
  sourceEvidenceIds: [],
  targetRole: "Product Engineer",
  template: "standard_professional",
  title: "Product resume",
  versionNumber: 4,
};

const resume: SavedResume = {
  createdAt: "2026-07-20T12:00:00Z",
  currentVersion: resumeVersion,
  currentVersionId: resumeVersion.id,
  id: resumeVersion.resumeId,
  layout: resumeVersion.layout,
  targetRole: "Product Engineer",
  template: "standard_professional",
  title: "Product resume",
  updatedAt: "2026-07-24T12:00:00Z",
  version: 3,
};

const alternateVersion: SavedResumeVersion = {
  ...resumeVersion,
  createdAt: "2026-07-25T12:00:00Z",
  id: "00000000-0000-4000-8000-000000008214",
  resumeId: "00000000-0000-4000-8000-000000008213",
  title: "Leadership resume",
  versionNumber: 2,
};

const alternateResume: SavedResume = {
  ...resume,
  currentVersion: alternateVersion,
  currentVersionId: alternateVersion.id,
  id: alternateVersion.resumeId,
  title: "Leadership resume",
};

const job: SavedJob = {
  applicationDeadline: "2026-08-01",
  company: "Example Co",
  compensation: null,
  createdAt: "2026-07-20T12:00:00Z",
  employmentType: "full_time",
  id: "00000000-0000-4000-8000-000000008202",
  location: "Remote",
  requirements: [],
  sourceKind: "url",
  sourceUrl: "https://example.test/jobs/product-engineer",
  targetRoleId: null,
  targetRoleTitle: null,
  title: "Product Engineer",
  updatedAt: "2026-07-24T12:00:00Z",
  version: 2,
  workModel: "remote",
};

const secondJob: SavedJob = {
  ...job,
  company: "Second Co",
  id: "00000000-0000-4000-8000-000000008212",
  title: "Staff Product Engineer",
};

const searchedJob: SavedJob = {
  ...job,
  company: "Leadership Co",
  id: "00000000-0000-4000-8000-000000008222",
  title: "Engineering Leader",
};

const created = {
  applicationDeadline: null,
  company: job.company,
  contacts: [],
  createdAt: "2026-07-24T12:00:00Z",
  evidencePins: [],
  eventCount: 1,
  followUpAt: null,
  id: "00000000-0000-4000-8000-000000008201",
  industry: "Software",
  jobAnalysisId: null,
  jobId: job.id,
  jobRequirements: [],
  jobSourceSha256: "a".repeat(64),
  jobTitle: job.title,
  jobVersion: job.version,
  location: job.location,
  noteCount: 0,
  offerSummary: null,
  openTaskCount: 0,
  outcomeStatus: "none",
  packCount: 0,
  referralStatus: "none",
  rejectionReason: null,
  resumeClaims: [],
  resumeEvidenceIds: [],
  resumeId: resume.id,
  resumeTitle: resume.title,
  resumeVersionId: resumeVersion.id,
  resumeVersionNumber: resumeVersion.versionNumber,
  source: "Referral",
  stage: "saved",
  taskCount: 0,
  updatedAt: "2026-07-24T12:00:00Z",
  version: 1,
} satisfies ApplicationDetail;

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

describe("Create application form", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listApplicationSourceJobs.mockResolvedValue({
      data: [job],
      page: { hasMore: false, limit: 25, nextCursor: null },
    });
    api.listApplicationSourceResumes.mockResolvedValue([resume]);
    api.listApplicationSourceResumeVersions.mockResolvedValue([resumeVersion]);
    api.createApplication.mockResolvedValue(created);
  });

  it("pins an explicit saved job and immutable resume version", async () => {
    const onCreated = vi.fn();
    render(<CreateApplicationForm onCreated={onCreated} />);

    expect(
      await screen.findByRole("option", {
        name: /Version 4 .*current/i,
      }),
    ).toBeVisible();
    fireEvent.change(screen.getByLabelText("Application source"), {
      target: { value: "Referral" },
    });
    fireEvent.change(screen.getByLabelText("Industry"), {
      target: { value: "Software" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add application" }));

    await waitFor(() => {
      expect(api.createApplication).toHaveBeenCalledWith(
        {
          applicationDeadline: null,
          contacts: [],
          followUpAt: null,
          industry: "Software",
          jobId: job.id,
          referralStatus: "none",
          resumeVersionId: resumeVersion.id,
          source: "Referral",
          stage: "saved",
        },
        expect.any(String),
      );
      expect(onCreated).toHaveBeenCalledWith(created);
    });
    expect(
      screen.queryByText("Application added", { selector: "p" }),
    ).not.toBeInTheDocument();
    expect(api.listApplicationSourceJobs).toHaveBeenCalledWith({ limit: 25 });
  });

  it("reuses an intent key for an unchanged retry and renews it after an edit", async () => {
    api.createApplication
      .mockRejectedValueOnce(new Error("response lost"))
      .mockResolvedValue(created);
    render(<CreateApplicationForm onCreated={vi.fn()} />);

    await screen.findByRole("option", { name: /Version 4 .*current/i });
    fireEvent.change(screen.getByLabelText("Application source"), {
      target: { value: "Referral" },
    });
    const submit = screen.getByRole("button", { name: "Add application" });
    fireEvent.click(submit);
    await waitFor(() => expect(api.createApplication).toHaveBeenCalledTimes(1));
    const firstKey = api.createApplication.mock.calls[0]?.[1];
    expect(firstKey).toEqual(expect.any(String));

    fireEvent.click(submit);
    await waitFor(() => expect(api.createApplication).toHaveBeenCalledTimes(2));
    expect(api.createApplication.mock.calls[1]?.[1]).toBe(firstKey);

    fireEvent.change(screen.getByLabelText("Industry"), {
      target: { value: "Software" },
    });
    fireEvent.click(submit);
    await waitFor(() => expect(api.createApplication).toHaveBeenCalledTimes(3));
    expect(api.createApplication.mock.calls[2]?.[1]).not.toBe(firstKey);
  });

  it("keeps the newest resume selection when version requests resolve out of order", async () => {
    const first = deferred<SavedResumeVersion[]>();
    const second = deferred<SavedResumeVersion[]>();
    api.listApplicationSourceResumes.mockResolvedValue([
      resume,
      alternateResume,
    ]);
    api.listApplicationSourceResumeVersions.mockImplementation(
      (resumeId: string) =>
        resumeId === resume.id ? first.promise : second.promise,
    );
    render(<CreateApplicationForm onCreated={vi.fn()} />);

    const resumeSelect = await screen.findByLabelText("Resume", {
      exact: true,
    });
    expect(
      await screen.findByRole("option", {
        name: "Loading resume versions...",
      }),
    ).toBeInTheDocument();
    fireEvent.change(resumeSelect, { target: { value: alternateResume.id } });

    await act(async () => {
      second.resolve([alternateVersion]);
      await second.promise;
    });
    expect(
      await screen.findByRole("option", {
        name: /Version 2 .*current/i,
      }),
    ).toBeVisible();

    await act(async () => {
      first.resolve([resumeVersion]);
      await first.promise;
    });
    expect(
      screen.getByRole("option", { name: /Version 2 .*current/i }),
    ).toBeVisible();
    expect(
      screen.queryByRole("option", { name: /Version 4/i }),
    ).not.toBeInTheDocument();
  });

  it("loads saved jobs in bounded pages and preserves the selected job across searches", async () => {
    const moreJobs = deferred<{
      data: SavedJob[];
      page: { hasMore: boolean; limit: number; nextCursor: string | null };
    }>();
    api.listApplicationSourceJobs
      .mockResolvedValueOnce({
        data: [job],
        page: { hasMore: true, limit: 25, nextCursor: "next-jobs" },
      })
      .mockReturnValueOnce(moreJobs.promise)
      .mockResolvedValueOnce({
        data: [searchedJob],
        page: { hasMore: false, limit: 25, nextCursor: null },
      });
    render(<CreateApplicationForm onCreated={vi.fn()} />);

    const savedJobSelect = await screen.findByLabelText("Saved job");
    expect(savedJobSelect).toHaveValue(job.id);
    const loadMoreButton = screen.getByRole("button", {
      name: "Load more saved jobs",
    });
    fireEvent.click(loadMoreButton);
    await waitFor(() =>
      expect(loadMoreButton).toHaveAttribute("aria-busy", "true"),
    );
    await act(async () => {
      moreJobs.resolve({
        data: [secondJob],
        page: { hasMore: false, limit: 25, nextCursor: null },
      });
      await moreJobs.promise;
    });

    expect(
      await screen.findByRole("option", { name: /Staff Product Engineer/i }),
    ).toBeVisible();
    expect(api.listApplicationSourceJobs).toHaveBeenNthCalledWith(2, {
      cursor: "next-jobs",
      limit: 25,
    });

    fireEvent.change(screen.getByLabelText("Search saved jobs"), {
      target: { value: "leader" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search jobs" }));

    expect(
      await screen.findByRole("option", { name: /Engineering Leader/i }),
    ).toBeVisible();
    expect(savedJobSelect).toHaveValue(job.id);
    expect(
      screen.getByRole("option", { name: /Product Engineer .*Example Co/i }),
    ).toBeVisible();
    expect(
      screen.queryByRole("option", { name: /Staff Product Engineer/i }),
    ).not.toBeInTheDocument();
    expect(api.listApplicationSourceJobs).toHaveBeenNthCalledWith(3, {
      limit: 25,
      q: "leader",
    });
  });

  it("ignores a late saved-job search response", async () => {
    const firstSearch = deferred<{
      data: SavedJob[];
      page: { hasMore: boolean; limit: number; nextCursor: string | null };
    }>();
    const secondSearch = deferred<{
      data: SavedJob[];
      page: { hasMore: boolean; limit: number; nextCursor: string | null };
    }>();
    api.listApplicationSourceJobs
      .mockResolvedValueOnce({
        data: [job],
        page: { hasMore: false, limit: 25, nextCursor: null },
      })
      .mockReturnValueOnce(firstSearch.promise)
      .mockReturnValueOnce(secondSearch.promise);
    render(<CreateApplicationForm onCreated={vi.fn()} />);

    await screen.findByLabelText("Saved job");
    const search = screen.getByLabelText("Search saved jobs");
    fireEvent.change(search, { target: { value: "staff" } });
    fireEvent.click(screen.getByRole("button", { name: "Search jobs" }));
    await waitFor(() =>
      expect(api.listApplicationSourceJobs).toHaveBeenCalledTimes(2),
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Searching saved jobs...",
    );

    fireEvent.change(search, { target: { value: "leader" } });
    fireEvent.click(screen.getByRole("button", { name: "Search jobs" }));
    await waitFor(() =>
      expect(api.listApplicationSourceJobs).toHaveBeenCalledTimes(3),
    );

    await act(async () => {
      secondSearch.resolve({
        data: [searchedJob],
        page: { hasMore: false, limit: 25, nextCursor: null },
      });
      await secondSearch.promise;
    });
    expect(
      await screen.findByRole("option", { name: /Engineering Leader/i }),
    ).toBeVisible();

    await act(async () => {
      firstSearch.resolve({
        data: [secondJob],
        page: { hasMore: false, limit: 25, nextCursor: null },
      });
      await firstSearch.promise;
    });
    expect(
      screen.getByRole("option", { name: /Engineering Leader/i }),
    ).toBeVisible();
    expect(
      screen.queryByRole("option", { name: /Staff Product Engineer/i }),
    ).not.toBeInTheDocument();
  });

  it("offers inline retry and an honest empty state for resume versions", async () => {
    api.listApplicationSourceResumeVersions
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce([]);
    render(<CreateApplicationForm onCreated={vi.fn()} />);

    expect(
      await screen.findByText("Resume versions unavailable", {
        selector: "p",
      }),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Retry resume versions" }),
    );

    expect(
      await screen.findByText("No immutable resume versions", {
        selector: "p",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Open resume builder" }),
    ).toHaveAttribute("href", "/resume-builder");
    expect(
      screen.getByRole("button", { name: "Add application" }),
    ).toBeDisabled();
  });
});
