import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  ApplicationDetail,
  ApplicationEvent,
  ApplicationNote,
  ApplicationPack,
  ApplicationTask,
  SavedResume,
  SavedResumeVersion,
} from "../api/types";
import { ApplicationDetailView } from "../views/application-detail-view";

const navigation = vi.hoisted(() => ({
  refresh: vi.fn(),
  replace: vi.fn(),
}));

const RequestConflictError = vi.hoisted(
  () =>
    class extends Error {
      failure = { status: 409 };
    },
);

const api = vi.hoisted(() => ({
  createApplicationEvent: vi.fn(),
  createApplicationNote: vi.fn(),
  createApplicationTask: vi.fn(),
  deleteApplication: vi.fn(),
  deleteApplicationDocument: vi.fn(),
  generateApplicationPack: vi.fn(),
  getApplication: vi.fn(),
  getApplicationConsistency: vi.fn(),
  getApplicationPack: vi.fn(),
  listApplicationEvents: vi.fn(),
  listApplicationNotes: vi.fn(),
  listApplicationPacks: vi.fn(),
  listApplicationSourceResumes: vi.fn(),
  listApplicationSourceResumeVersions: vi.fn(),
  listApplicationTasks: vi.fn(),
  updateApplication: vi.fn(),
  updateApplicationStage: vi.fn(),
  updateApplicationTask: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => navigation,
}));

vi.mock("../api/applications-api", () => ({
  ApiRequestError: RequestConflictError,
  ...api,
}));

const applicationId = "00000000-0000-4000-8000-000000008101";

const application: ApplicationDetail = {
  applicationDeadline: "2026-08-01",
  company: "Example Co",
  contacts: [
    {
      email: "recruiter@example.test",
      name: "Fictional Recruiter",
      role: "Recruiter",
      url: null,
    },
  ],
  createdAt: "2026-07-20T12:00:00Z",
  evidencePins: [
    {
      evidenceId: "00000000-0000-4000-8000-000000008110",
      evidenceRevisionId: "00000000-0000-4000-8000-000000008111",
      hasNumericClaim: false,
      revisionNumber: 2,
      statement: "Built an accessible product workflow.",
      statementSha256: "b".repeat(64),
      strength: "confirmed",
    },
  ],
  eventCount: 1,
  followUpAt: "2026-07-27",
  id: applicationId,
  industry: "Software",
  jobAnalysisId: null,
  jobId: "00000000-0000-4000-8000-000000008102",
  jobRequirements: [
    {
      id: "00000000-0000-4000-8000-000000008113",
      importance: "mandatory",
      requirementType: "experience",
      sourceEnd: 42,
      sourceStart: 2,
      text: "Experience building accessible product workflows.",
    },
  ],
  jobSourceSha256: "a".repeat(64),
  jobTitle: "Product Engineer",
  jobVersion: 2,
  location: "Remote",
  noteCount: 0,
  offerSummary: null,
  openTaskCount: 0,
  outcomeStatus: "none",
  packCount: 0,
  referralStatus: "requested",
  rejectionReason: null,
  resumeClaims: [
    {
      evidenceLinks: [
        {
          evidenceId: "00000000-0000-4000-8000-000000008110",
          evidenceRevisionId: "00000000-0000-4000-8000-000000008111",
        },
      ],
      id: "00000000-0000-4000-8000-000000008114",
      requirementIds: ["00000000-0000-4000-8000-000000008113"],
      text: "Built an accessible product workflow.",
    },
  ],
  resumeEvidenceIds: ["00000000-0000-4000-8000-000000008110"],
  resumeId: "00000000-0000-4000-8000-000000008103",
  resumeTitle: "Product resume",
  resumeVersionId: "00000000-0000-4000-8000-000000008104",
  resumeVersionNumber: 4,
  source: "Referral",
  stage: "preparing",
  taskCount: 0,
  updatedAt: "2026-07-24T12:00:00Z",
  version: 3,
};

const createdEvent: ApplicationEvent = {
  applicationId,
  createdAt: "2026-07-20T12:00:00Z",
  description: null,
  eventKind: "created",
  id: "00000000-0000-4000-8000-000000008112",
  metadata: {},
  occurredAt: "2026-07-20T12:00:00Z",
  title: "Application created",
};

const note: ApplicationNote = {
  applicationId,
  body: "Review the evidence.",
  createdAt: "2026-07-24T12:00:00Z",
  id: "00000000-0000-4000-8000-000000008115",
};

const contactEvent: ApplicationEvent = {
  ...createdEvent,
  eventKind: "contact",
  id: "00000000-0000-4000-8000-000000008116",
  title: "Recruiter conversation",
};

const task: ApplicationTask = {
  applicationId,
  completedAt: null,
  createdAt: "2026-07-24T12:00:00Z",
  dueAt: "2026-07-30",
  id: "00000000-0000-4000-8000-000000008120",
  title: "Prepare examples",
  updatedAt: "2026-07-24T12:00:00Z",
  version: 1,
};

const pack: ApplicationPack = {
  applicationId,
  applicationVersion: 3,
  consistencyFindings: [],
  consistencyStatus: "passed",
  createdAt: "2026-07-24T12:00:00Z",
  documents: [],
  evidenceRevisionIds: ["00000000-0000-4000-8000-000000008111"],
  id: "00000000-0000-4000-8000-000000008130",
  jobId: application.jobId,
  jobVersion: application.jobVersion,
  requirementIds: ["00000000-0000-4000-8000-000000008113"],
  resumeVersionId: application.resumeVersionId,
  resumeVersionNumber: application.resumeVersionNumber,
  status: "generated",
};

const alternateVersion: SavedResumeVersion = {
  createdAt: "2026-07-25T12:00:00Z",
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
  parentVersionId: application.resumeVersionId,
  personalFacts: [],
  plainText: "Product leadership resume",
  resumeId: application.resumeId,
  sections: [],
  sourceChangeSetId: null,
  sourceChangeSetVersionId: null,
  sourceEvidenceIds: [],
  targetRole: "Product Lead",
  template: "standard_professional",
  title: application.resumeTitle,
  versionNumber: 5,
};

const savedResume: SavedResume = {
  createdAt: application.createdAt,
  currentVersion: alternateVersion,
  currentVersionId: alternateVersion.id,
  id: application.resumeId,
  layout: alternateVersion.layout,
  targetRole: "Product Lead",
  template: "standard_professional",
  title: application.resumeTitle,
  updatedAt: alternateVersion.createdAt,
  version: 4,
};

const emptyPage = {
  data: [],
  page: { hasMore: false, limit: 25, nextCursor: null },
};

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal() {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function close() {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
});

describe("Application detail workflow", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    api.getApplication.mockResolvedValue(application);
    api.createApplicationEvent.mockResolvedValue(contactEvent);
    api.createApplicationNote.mockResolvedValue(note);
    api.createApplicationTask.mockResolvedValue(task);
    api.generateApplicationPack.mockResolvedValue(pack);
    api.getApplicationPack.mockResolvedValue(pack);
    api.listApplicationTasks.mockResolvedValue(emptyPage);
    api.listApplicationNotes.mockResolvedValue(emptyPage);
    api.listApplicationEvents.mockResolvedValue({
      ...emptyPage,
      data: [createdEvent],
      page: { ...emptyPage.page, limit: 50 },
    });
    api.listApplicationPacks.mockResolvedValue(emptyPage);
    api.listApplicationSourceResumes.mockResolvedValue([savedResume]);
    api.listApplicationSourceResumeVersions.mockResolvedValue([
      {
        ...alternateVersion,
        id: application.resumeVersionId,
        versionNumber: application.resumeVersionNumber,
      },
      alternateVersion,
    ]);
    api.updateApplication.mockResolvedValue({
      ...application,
      source: "Company site",
      version: 4,
    });
    api.updateApplicationStage.mockResolvedValue({
      ...application,
      stage: "applied",
      version: 4,
    });
    api.updateApplicationTask.mockResolvedValue({
      ...task,
      completedAt: "2026-07-25T12:00:00Z",
      version: 2,
    });
  });

  it("shows exact source pins and saves editable workflow fields", async () => {
    render(<ApplicationDetailView applicationId={applicationId} />);

    expect(
      await screen.findByRole("heading", { name: "Product Engineer" }),
    ).toBeVisible();
    expect(screen.getByText("Immutable version 4")).toBeVisible();
    expect(screen.getByText("1 exact revisions")).toBeVisible();
    expect(
      screen.getByText("Built an accessible product workflow."),
    ).toBeVisible();

    fireEvent.change(screen.getByLabelText("Application source"), {
      target: { value: "Company site" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Save workflow details" }),
    );

    expect(api.updateApplication).toHaveBeenCalledWith(
      application,
      expect.objectContaining({
        industry: "Software",
        source: "Company site",
      }),
    );
    const savedMessage = await screen.findByText("Application details saved.");
    expect(savedMessage).toBeVisible();
    expect(savedMessage.closest('[role="status"]')).not.toBeNull();
    expect(screen.getAllByText("Application details saved.")).toHaveLength(1);
  });

  it("keeps contact input identity and focus while the name changes", async () => {
    render(<ApplicationDetailView applicationId={applicationId} />);
    await screen.findByRole("heading", { name: "Product Engineer" });

    const nameInput = screen.getByLabelText("Name");
    nameInput.focus();
    fireEvent.change(nameInput, {
      target: { value: "Fictional Hiring Manager" },
    });

    expect(nameInput).toHaveFocus();
    expect(screen.getByLabelText("Name")).toBe(nameInput);
    expect(nameInput).toHaveValue("Fictional Hiring Manager");
    expect(
      screen.getByRole("group", {
        name: "Contact 1: Fictional Hiring Manager",
      }),
    ).toContainElement(nameInput);
  });

  it("preserves unsaved overview fields across aggregate version updates", async () => {
    render(<ApplicationDetailView applicationId={applicationId} />);
    await screen.findByRole("heading", { name: "Product Engineer" });

    const sourceInput = screen.getByLabelText("Application source");
    fireEvent.change(sourceInput, {
      target: { value: "Unsaved networking referral" },
    });
    fireEvent.change(screen.getByLabelText("Move to stage"), {
      target: { value: "applied" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Move" }));

    expect(
      await screen.findByText("Application moved to Applied."),
    ).toBeVisible();
    expect(api.updateApplicationStage).toHaveBeenCalledWith(application, {
      stage: "applied",
    });
    expect(screen.getByLabelText("Application source")).toBe(sourceInput);
    expect(sourceInput).toHaveValue("Unsaved networking referral");
  });

  it("synchronizes the stage control when an outcome changes the stage", async () => {
    api.updateApplication.mockResolvedValueOnce({
      ...application,
      outcomeStatus: "offer",
      stage: "offer",
      version: 4,
    });
    render(<ApplicationDetailView applicationId={applicationId} />);
    await screen.findByRole("heading", { name: "Product Engineer" });

    fireEvent.change(screen.getByLabelText(/^Outcome/), {
      target: { value: "offer" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Save workflow details" }),
    );

    expect(await screen.findByText("Application details saved.")).toBeVisible();
    await waitFor(() => {
      expect(screen.getByLabelText("Move to stage")).toHaveValue("offer");
      expect(screen.getByRole("button", { name: "Move" })).toBeDisabled();
    });
  });

  it("loads hidden tabs on first visit and preserves their mounted drafts", async () => {
    render(<ApplicationDetailView applicationId={applicationId} />);
    await screen.findByRole("heading", { name: "Product Engineer" });

    expect(api.listApplicationTasks).not.toHaveBeenCalled();
    expect(api.listApplicationNotes).not.toHaveBeenCalled();
    expect(api.listApplicationEvents).not.toHaveBeenCalled();
    expect(api.listApplicationPacks).not.toHaveBeenCalled();

    fireEvent.click(
      screen.getByRole("tab", { name: /Tasks, notes & timeline/i }),
    );
    await waitFor(() => {
      expect(api.listApplicationTasks).toHaveBeenCalledTimes(1);
      expect(api.listApplicationNotes).toHaveBeenCalledTimes(1);
      expect(api.listApplicationEvents).toHaveBeenCalledTimes(1);
    });
    expect(api.listApplicationPacks).not.toHaveBeenCalled();

    const noteDraft = screen.getByLabelText("Add a private application note");
    fireEvent.change(noteDraft, {
      target: { value: "Keep this private note draft." },
    });

    fireEvent.click(screen.getByRole("tab", { name: /Application packs/i }));
    await waitFor(() => {
      expect(api.listApplicationPacks).toHaveBeenCalledTimes(1);
    });
    fireEvent.click(screen.getByRole("tab", { name: "Overview" }));
    fireEvent.click(
      screen.getByRole("tab", { name: /Tasks, notes & timeline/i }),
    );

    expect(screen.getByLabelText("Add a private application note")).toBe(
      noteDraft,
    );
    expect(noteDraft).toHaveValue("Keep this private note draft.");
    expect(api.listApplicationTasks).toHaveBeenCalledTimes(1);
    expect(api.listApplicationNotes).toHaveBeenCalledTimes(1);
    expect(api.listApplicationEvents).toHaveBeenCalledTimes(1);
    expect(api.listApplicationPacks).toHaveBeenCalledTimes(1);
  });

  it("resets overview drafts and refreshes mounted child panels on an explicit conflict reload", async () => {
    const reloadedTask = {
      ...task,
      id: "00000000-0000-4000-8000-000000008122",
      title: "Fresh task from another session",
      version: 2,
    };
    const reloadedApplication = {
      ...application,
      contacts: [
        {
          email: "fresh@example.test",
          name: "Fresh Remote Contact",
          role: "Hiring manager",
          url: null,
        },
      ],
      industry: "Fresh remote industry",
      source: "Fresh remote source",
      version: 4,
    } satisfies ApplicationDetail;
    api.getApplication
      .mockResolvedValueOnce(application)
      .mockResolvedValueOnce(reloadedApplication);
    api.listApplicationTasks
      .mockResolvedValueOnce({
        data: [task],
        page: { hasMore: false, limit: 25, nextCursor: null },
      })
      .mockResolvedValueOnce({
        data: [reloadedTask],
        page: { hasMore: false, limit: 25, nextCursor: null },
      });
    api.updateApplication.mockRejectedValueOnce(new RequestConflictError());
    render(<ApplicationDetailView applicationId={applicationId} />);
    await screen.findByRole("heading", { name: "Product Engineer" });

    fireEvent.click(
      screen.getByRole("tab", { name: /Tasks, notes & timeline/i }),
    );
    expect(await screen.findByDisplayValue(task.title)).toBeVisible();
    fireEvent.click(screen.getByRole("tab", { name: /Application packs/i }));
    await waitFor(() =>
      expect(api.listApplicationPacks).toHaveBeenCalledTimes(1),
    );
    fireEvent.click(screen.getByRole("tab", { name: "Overview" }));

    fireEvent.change(screen.getByLabelText("Application source"), {
      target: { value: "Unsaved local source" },
    });
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Unsaved Local Contact" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Save workflow details" }),
    );
    const reload = await screen.findByRole("button", {
      name: "Reload current data",
    });
    fireEvent.click(reload);

    await waitFor(() => {
      expect(screen.getByLabelText("Application source")).toHaveValue(
        reloadedApplication.source,
      );
      expect(screen.getByLabelText("Name")).toHaveValue(
        reloadedApplication.contacts[0]?.name,
      );
      expect(api.listApplicationTasks).toHaveBeenCalledTimes(2);
      expect(api.listApplicationNotes).toHaveBeenCalledTimes(2);
      expect(api.listApplicationEvents).toHaveBeenCalledTimes(2);
      expect(api.listApplicationPacks).toHaveBeenCalledTimes(2);
    });
    expect(
      screen.getByDisplayValue("Fresh task from another session"),
    ).toBeInTheDocument();
    expect(screen.queryByDisplayValue(task.title)).not.toBeInTheDocument();
  });

  it("requires a reason and explicit confirmation to change the pinned resume", async () => {
    render(<ApplicationDetailView applicationId={applicationId} />);
    await screen.findByRole("heading", { name: "Product Engineer" });

    const sourceInput = screen.getByLabelText("Application source");
    fireEvent.change(sourceInput, {
      target: { value: "Unsaved source change" },
    });
    const resumeChangeSummary = screen.getByText(
      "Change pinned resume version",
    );
    const resumeChangeDetails = resumeChangeSummary.closest("details");
    expect(resumeChangeDetails).not.toBeNull();
    resumeChangeDetails!.open = true;
    fireEvent(resumeChangeDetails!, new Event("toggle"));
    const versionOption = await screen.findByRole("option", {
      name: /Product resume, version 5/i,
    });
    fireEvent.change(screen.getByLabelText("New immutable resume version"), {
      target: { value: versionOption.getAttribute("value") },
    });

    const reviewButton = screen.getByRole("button", {
      name: "Review resume version change",
    });
    expect(reviewButton).toBeDisabled();
    fireEvent.change(
      screen.getByLabelText(/Reason for changing the pinned resume/),
      {
        target: {
          value: "Use the newly confirmed leadership evidence.",
        },
      },
    );
    expect(reviewButton).toBeEnabled();
    fireEvent.click(reviewButton);

    expect(
      await screen.findByRole("dialog", {
        name: "Confirm pinned resume change",
      }),
    ).toHaveAccessibleDescription(
      /Use the newly confirmed leadership evidence/i,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Change pinned version" }),
    );

    await waitFor(() => {
      expect(api.updateApplication).toHaveBeenCalledWith(application, {
        resumeChangeReason: "Use the newly confirmed leadership evidence.",
        resumeVersionId: alternateVersion.id,
      });
    });
    expect(screen.getByLabelText("Application source")).toBe(sourceInput);
    expect(sourceInput).toHaveValue("Unsaved source change");
  });

  it("adds a task and generates only explicitly selected draft documents", async () => {
    render(<ApplicationDetailView applicationId={applicationId} />);
    await screen.findByRole("heading", { name: "Product Engineer" });

    fireEvent.click(
      screen.getByRole("tab", { name: /Tasks, notes & timeline/i }),
    );
    fireEvent.change(screen.getByLabelText("Task"), {
      target: { value: "Prepare examples" },
    });
    fireEvent.change(screen.getByLabelText("Due date"), {
      target: { value: "2026-07-30" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));

    expect(api.createApplicationTask).toHaveBeenCalledWith(
      applicationId,
      {
        dueAt: "2026-07-30",
        title: "Prepare examples",
      },
      expect.any(String),
    );
    expect(await screen.findByDisplayValue("Prepare examples")).toBeVisible();
    expect(
      screen.getByRole("tab", {
        name: "Tasks, notes & timeline (1)",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("group", { name: "Edit task: Prepare examples" }),
    ).toBeVisible();

    fireEvent.click(
      screen.getByRole("button", { name: "Complete Prepare examples" }),
    );
    expect(
      await screen.findByRole("tab", {
        name: "Tasks, notes & timeline (0)",
      }),
    ).toBeVisible();

    fireEvent.click(screen.getByRole("tab", { name: /Application packs/i }));
    fireEvent.click(
      screen.getByRole("button", { name: "Generate grounded drafts" }),
    );

    expect(api.generateApplicationPack).toHaveBeenCalledWith(
      applicationId,
      {
        includeKinds: ["tailored_resume", "cover_letter"],
      },
      expect.any(String),
    );
    expect(
      await screen.findByRole("tab", { name: "Application packs (1)" }),
    ).toBeVisible();
    const generatedMessage = await screen.findByText(
      /Application pack generated from the pinned job/i,
    );
    expect(generatedMessage.closest('[role="status"]')).not.toBeNull();
  });

  it("reuses idempotency keys when unchanged task and pack intents are retried", async () => {
    api.createApplicationTask
      .mockRejectedValueOnce(new Error("response lost"))
      .mockResolvedValue(task);
    api.generateApplicationPack
      .mockRejectedValueOnce(new Error("response lost"))
      .mockResolvedValue(pack);
    render(<ApplicationDetailView applicationId={applicationId} />);
    await screen.findByRole("heading", { name: "Product Engineer" });

    fireEvent.click(
      screen.getByRole("tab", { name: /Tasks, notes & timeline/i }),
    );
    fireEvent.change(screen.getByLabelText("Task"), {
      target: { value: "Prepare examples" },
    });
    const addTask = screen.getByRole("button", { name: "Add" });
    fireEvent.click(addTask);
    await waitFor(() =>
      expect(api.createApplicationTask).toHaveBeenCalledTimes(1),
    );
    const taskKey = api.createApplicationTask.mock.calls[0]?.[2];
    fireEvent.click(addTask);
    await waitFor(() =>
      expect(api.createApplicationTask).toHaveBeenCalledTimes(2),
    );
    expect(api.createApplicationTask.mock.calls[1]?.[2]).toBe(taskKey);

    fireEvent.click(screen.getByRole("tab", { name: /Application packs/i }));
    const generate = screen.getByRole("button", {
      name: "Generate grounded drafts",
    });
    fireEvent.click(generate);
    await waitFor(() =>
      expect(api.generateApplicationPack).toHaveBeenCalledTimes(1),
    );
    const packKey = api.generateApplicationPack.mock.calls[0]?.[2];
    fireEvent.click(generate);
    await waitFor(() =>
      expect(api.generateApplicationPack).toHaveBeenCalledTimes(2),
    );
    expect(api.generateApplicationPack.mock.calls[1]?.[2]).toBe(packKey);
  });

  it("reuses idempotency keys when unchanged note and event intents are retried", async () => {
    api.createApplicationNote
      .mockRejectedValueOnce(new Error("response lost"))
      .mockResolvedValue(note);
    api.createApplicationEvent
      .mockRejectedValueOnce(new Error("response lost"))
      .mockResolvedValue(contactEvent);
    render(<ApplicationDetailView applicationId={applicationId} />);
    await screen.findByRole("heading", { name: "Product Engineer" });
    fireEvent.click(
      screen.getByRole("tab", { name: /Tasks, notes & timeline/i }),
    );

    fireEvent.change(screen.getByLabelText("Add a private application note"), {
      target: { value: note.body },
    });
    const addNote = screen.getByRole("button", { name: "Add note" });
    fireEvent.click(addNote);
    await waitFor(() =>
      expect(api.createApplicationNote).toHaveBeenCalledTimes(1),
    );
    const noteKey = api.createApplicationNote.mock.calls[0]?.[2];
    fireEvent.click(addNote);
    await waitFor(() =>
      expect(api.createApplicationNote).toHaveBeenCalledTimes(2),
    );
    expect(api.createApplicationNote.mock.calls[1]?.[2]).toBe(noteKey);

    fireEvent.change(screen.getByLabelText("Event type"), {
      target: { value: "contact" },
    });
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: contactEvent.title },
    });
    const recordEvent = screen.getByRole("button", { name: "Record event" });
    fireEvent.click(recordEvent);
    await waitFor(() =>
      expect(api.createApplicationEvent).toHaveBeenCalledTimes(1),
    );
    const eventKey = api.createApplicationEvent.mock.calls[0]?.[2];
    fireEvent.click(recordEvent);
    await waitFor(() =>
      expect(api.createApplicationEvent).toHaveBeenCalledTimes(2),
    );
    expect(api.createApplicationEvent.mock.calls[1]?.[2]).toBe(eventKey);
  });

  it("loads bounded activity pages independently and can fetch more tasks", async () => {
    const laterTask = {
      ...task,
      id: "00000000-0000-4000-8000-000000008121",
      title: "Review role requirements",
    };
    api.listApplicationTasks
      .mockResolvedValueOnce({
        data: [task],
        page: { hasMore: true, limit: 25, nextCursor: "next-tasks" },
      })
      .mockResolvedValueOnce({
        data: [laterTask],
        page: { hasMore: false, limit: 25, nextCursor: null },
      });
    api.listApplicationNotes.mockRejectedValueOnce(new Error("offline"));

    render(<ApplicationDetailView applicationId={applicationId} />);
    await screen.findByRole("heading", { name: "Product Engineer" });
    fireEvent.click(
      screen.getByRole("tab", { name: /Tasks, notes & timeline/i }),
    );

    expect(await screen.findByDisplayValue(task.title)).toBeVisible();
    expect(
      await screen.findByText("Notes unavailable", { selector: "p" }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Load more tasks" }));

    expect(await screen.findByDisplayValue(laterTask.title)).toBeVisible();
    expect(api.listApplicationTasks).toHaveBeenLastCalledWith(applicationId, {
      cursor: "next-tasks",
      limit: 25,
    });
  });

  it("fetches full pack documents only when a listed pack is expanded", async () => {
    api.listApplicationPacks.mockResolvedValueOnce({
      data: [pack],
      page: { hasMore: false, limit: 25, nextCursor: null },
    });

    render(<ApplicationDetailView applicationId={applicationId} />);
    await screen.findByRole("heading", { name: "Product Engineer" });
    fireEvent.click(screen.getByRole("tab", { name: /Application packs/i }));
    expect(await screen.findByText(/Pack from/i)).toBeVisible();
    expect(api.getApplicationPack).not.toHaveBeenCalled();

    fireEvent.click(screen.getByText("View generated documents"));

    await waitFor(() => {
      expect(api.getApplicationPack).toHaveBeenCalledWith(pack.id);
    });
    expect(
      await screen.findByText("This pack contains no displayable documents."),
    ).toBeVisible();
  });

  it("renders a retryable detail failure", async () => {
    api.getApplication.mockRejectedValue(new Error("offline"));
    render(<ApplicationDetailView applicationId={applicationId} />);

    expect(
      await screen.findByRole("heading", { name: "Application unavailable" }),
    ).toBeVisible();
  });
});
