import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  CareerProfile,
  Experience,
  ProfileImportProposal,
} from "../api/types";
import { CareerProfileView } from "../views/career-profile-view";
import { ProfileImportReviewView } from "../views/profile-import-review-view";

const api = vi.hoisted(() => ({
  acceptProfileImportProposal: vi.fn(),
  createExperience: vi.fn(),
  getCareerItems: vi.fn(),
  getCareerProfile: vi.fn(),
  getExperiences: vi.fn(),
  getProfileImportProposal: vi.fn(),
  getSkills: vi.fn(),
  reorderExperiences: vi.fn(),
  rejectProfileImportProposal: vi.fn(),
}));

vi.mock("../api/career-vault-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/career-vault-api")>()),
  createExperience: api.createExperience,
  acceptProfileImportProposal: api.acceptProfileImportProposal,
  getCareerItems: api.getCareerItems,
  getCareerProfile: api.getCareerProfile,
  getExperiences: api.getExperiences,
  getProfileImportProposal: api.getProfileImportProposal,
  getSkills: api.getSkills,
  reorderExperiences: api.reorderExperiences,
  rejectProfileImportProposal: api.rejectProfileImportProposal,
}));

const profile: CareerProfile = {
  accountPreferences: {
    displayName: "Alex Example",
    email: "alex@example.test",
    industry: null,
    language: "en",
    preferredLocation: null,
    seniority: null,
    targetRole: null,
    workModel: null,
  },
  createdAt: "2026-07-15T00:00:00Z",
  id: "00000000-0000-4000-8000-000000000101",
  professionalHeadline: "",
  professionalSummary: "",
  updatedAt: "2026-07-15T00:00:00Z",
  version: 1,
  workAuthorization: "",
};

const savedExperience: Experience = {
  concurrentGroupId: null,
  conflicts: [],
  createdAt: "2026-07-15T00:00:00Z",
  current: true,
  description: "",
  displayTitle: null,
  employer: "Fictional Co",
  employmentType: "full_time",
  endDate: null,
  id: "00000000-0000-4000-8000-000000000102",
  location: null,
  officialTitle: "Engineer",
  order: 0,
  promotionGroupId: null,
  provenance: [],
  skillIds: [],
  startDate: "2024-04",
  updatedAt: "2026-07-15T00:00:00Z",
  userConfirmed: true,
  version: 1,
};

const proposal: ProfileImportProposal = {
  changes: [
    {
      conflict: "Different current value",
      currentValue: "Current summary",
      field: "professionalSummary",
      id: "00000000-0000-4000-8000-000000000104",
      label: "Professional summary",
      proposedValue: "Proposed summary",
      source: {
        available: true,
        confidence: 90,
        id: "00000000-0000-4000-8000-000000000105",
        parserVersion: "fictional-parser/1",
        sourceDocumentId: "00000000-0000-4000-8000-000000000106",
        sourceLabel: "fictional-resume.pdf",
        sourceRevision: 1,
        sourceSnapshotId: "00000000-0000-4000-8000-000000000107",
        sourceType: "resume",
        spans: [],
        userConfirmed: false,
      },
    },
  ],
  createdAt: "2026-07-15T00:00:00Z",
  id: "00000000-0000-4000-8000-000000000103",
  sourceDocumentName: "fictional-resume.pdf",
  status: "pending",
  version: 1,
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

describe("Career Profile vertical slice", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getCareerProfile.mockResolvedValue(profile);
    api.getExperiences.mockResolvedValue([]);
    api.getCareerItems.mockResolvedValue([]);
    api.getSkills.mockResolvedValue([]);
    api.getProfileImportProposal.mockResolvedValue(proposal);
    api.createExperience.mockResolvedValue(savedExperience);
    api.acceptProfileImportProposal.mockResolvedValue({
      ...proposal,
      status: "accepted",
    });
  });

  it("loads real empty collections and adds a year-month experience", async () => {
    render(<CareerProfileView />);

    expect(
      await screen.findByRole("heading", { name: "Career Profile" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Your career timeline is empty" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "No typed career records yet" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "No skills added" }),
    ).toBeVisible();

    fireEvent.click(
      screen.getAllByRole("button", { name: "Add experience" }).at(-1)!,
    );
    fireEvent.change(screen.getByLabelText("Employer"), {
      target: { value: "Fictional Co" },
    });
    fireEvent.change(screen.getByLabelText("Official title"), {
      target: { value: "Engineer" },
    });
    fireEvent.change(screen.getByLabelText("Start month"), {
      target: { value: "2024-04" },
    });
    fireEvent.change(screen.getByLabelText("Employment type (optional)"), {
      target: { value: "full_time" },
    });
    api.getExperiences.mockResolvedValue([savedExperience]);
    fireEvent.click(
      screen.getAllByRole("button", { name: "Add experience" }).at(-1)!,
    );

    await waitFor(() =>
      expect(api.createExperience).toHaveBeenCalledWith({
        current: true,
        description: "",
        displayTitle: null,
        employer: "Fictional Co",
        employmentType: "full_time",
        endDate: null,
        groupWithExperienceId: null,
        location: null,
        officialTitle: "Engineer",
        skillIds: [],
        startDate: "2024-04",
      }),
    );
    expect(
      await screen.findByText("Experience added to your career profile."),
    ).toBeVisible();
  });

  it("renders a safe retry state when owned profile loading fails", async () => {
    api.getCareerProfile.mockRejectedValueOnce(new Error("offline"));
    render(<CareerProfileView />);

    expect(
      await screen.findByRole("heading", {
        name: "Career profile unavailable",
      }),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();
  });

  it("shows current and proposed values without applying until explicit confirmation", async () => {
    render(<ProfileImportReviewView proposalId={proposal.id} />);

    expect(await screen.findByText("Current summary")).toBeVisible();
    expect(screen.getByDisplayValue("Proposed summary")).toBeVisible();
    expect(api.acceptProfileImportProposal).not.toHaveBeenCalled();

    fireEvent.click(
      screen.getByRole("button", { name: "Accept reviewed changes" }),
    );
    expect(api.acceptProfileImportProposal).not.toHaveBeenCalled();
    expect(
      screen.getByRole("dialog", { name: "Apply these reviewed changes?" }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Accept changes" }));

    await waitFor(() =>
      expect(api.acceptProfileImportProposal).toHaveBeenCalledWith(proposal, {
        [proposal.changes[0]!.id]: "Proposed summary",
      }),
    );
  });
});
