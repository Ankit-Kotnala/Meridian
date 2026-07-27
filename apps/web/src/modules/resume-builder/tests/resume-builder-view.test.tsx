import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Resume, ResumeExportRecord, ResumeVersion } from "../api/types";
import { ResumeBuilderView } from "../views/resume-builder-view";

const api = vi.hoisted(() => ({
  createDownloadIntent: vi.fn(),
  createResume: vi.fn(),
  createVersion: vi.fn(),
  deleteExport: vi.fn(),
  exportVersion: vi.fn(),
  getExport: vi.fn(),
  getResumeSourceOptions: vi.fn(),
  listResumes: vi.fn(),
  listVersions: vi.fn(),
  restoreVersion: vi.fn(),
  updateResume: vi.fn(),
}));

vi.mock("../api/resume-builder-api", () => api);

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((next) => {
    resolve = next;
  });
  return { promise, resolve };
}

const baseVersion: ResumeVersion = {
  createdAt: "2026-07-19T12:00:00Z",
  entities: [],
  id: "00000000-0000-4000-8000-000000000801",
  layout: {
    fontFamily: "sans",
    fontSizePt: 10,
    lineSpacing: "standard",
    margins: "standard",
    pageLimit: 1,
    pageSize: "letter",
  },
  parentVersionId: null,
  personalFacts: [
    {
      id: "00000000-0000-4000-8000-000000000808",
      isPrimary: true,
      kind: "name",
      label: null,
      value: "Taylor Morgan",
    },
  ],
  plainText:
    "API Resume\nSenior Product Manager\nExperience\nConfirmed product discovery work across customer interviews.",
  resumeId: "00000000-0000-4000-8000-000000000802",
  sections: [
    {
      id: "00000000-0000-4000-8000-000000000803",
      items: [
        {
          entityId: null,
          evidenceIds: ["00000000-0000-4000-8000-000000000804"],
          evidenceReferences: [
            {
              claimSha256: "d".repeat(64),
              evidenceId: "00000000-0000-4000-8000-000000000804",
              evidenceRevisionId: "00000000-0000-4000-8000-000000000807",
              linkBasis: "evidence_statement",
              revisionNumber: 1,
              sourceSkillId: null,
              statementSha256: "e".repeat(64),
            },
          ],
          id: "00000000-0000-4000-8000-000000000805",
          source: "career_record",
          text: "Confirmed product discovery work across customer interviews.",
        },
      ],
      kind: "experience",
      title: "Experience",
    },
  ],
  sourceChangeSetId: null,
  sourceChangeSetVersionId: null,
  sourceEvidenceIds: ["00000000-0000-4000-8000-000000000804"],
  targetRole: "Senior Product Manager",
  template: "standard_professional",
  title: "API Resume",
  versionNumber: 1,
};

const baseResume: Resume = {
  createdAt: "2026-07-19T12:00:00Z",
  currentVersion: baseVersion,
  currentVersionId: baseVersion.id,
  id: baseVersion.resumeId,
  layout: baseVersion.layout,
  targetRole: "Senior Product Manager",
  template: "standard_professional",
  title: "API Resume",
  updatedAt: "2026-07-19T12:00:00Z",
  version: 1,
};

const verifiedExport: ResumeExportRecord = {
  export: {
    attempts: 1,
    cleanupAttempts: 0,
    cleanupMaxAttempts: 3,
    completedAt: "2026-07-19T12:00:01Z",
    criticalFailures: [],
    deadLetteredAt: null,
    deletedAt: null,
    fidelityManifestSha256: "b".repeat(64),
    format: "pdf",
    id: "00000000-0000-4000-8000-000000000806",
    mediaType: "application/pdf",
    lastError: null,
    maxAttempts: 3,
    parserVersion: "test-parser",
    rendererVersion: "test-renderer",
    requestedAt: "2026-07-19T12:00:00Z",
    retryAt: null,
    resumeId: baseResume.id,
    sha256Digest: "a".repeat(64),
    sizeBytes: 1024,
    status: "verified",
    verificationCodes: ["round_trip_searchable"],
    verificationStatus: "passed",
    versionId: baseVersion.id,
    versionContentSha256: "c".repeat(64),
    warnings: [],
  },
  verification: {
    createdAt: "2026-07-19T12:00:01Z",
    criticalFailures: [],
    detectedLines: ["API Resume"],
    duplicateLines: [],
    exportId: "00000000-0000-4000-8000-000000000806",
    fileSha256: "a".repeat(64),
    groundingCodes: ["all_bullets_grounded"],
    id: "00000000-0000-4000-8000-000000000807",
    manifestSha256: "b".repeat(64),
    missingLines: [],
    occurrenceMismatches: [],
    pageCount: 1,
    parserVersion: "test-parser",
    readingOrder: ["API Resume"],
    readingOrderFailures: [],
    status: "passed",
    versionId: baseVersion.id,
    versionContentSha256: "c".repeat(64),
    warnings: [],
  },
};

describe("Resume Builder view", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listResumes.mockResolvedValue([]);
    api.listVersions.mockResolvedValue([]);
    api.getResumeSourceOptions.mockResolvedValue({
      bullets: [
        {
          entityId: null,
          evidenceIds: ["00000000-0000-4000-8000-000000000804"],
          evidenceReferences:
            baseVersion.sections[0]!.items[0]!.evidenceReferences,
          sectionKind: "experience",
          source: "career_record",
          text: "Confirmed product discovery work across customer interviews.",
        },
      ],
      entities: [],
      headline: null,
      personalFacts: baseVersion.personalFacts,
      skills: [],
      sourceEvidenceIds: baseVersion.sourceEvidenceIds,
      summary: null,
    });
    api.createResume.mockResolvedValue(baseResume);
    api.updateResume.mockResolvedValue({ ...baseResume, version: 2 });
    api.createVersion.mockResolvedValue({ ...baseVersion, versionNumber: 2 });
    api.deleteExport.mockResolvedValue({
      ...verifiedExport,
      export: {
        ...verifiedExport.export,
        status: "deletion_pending",
      },
    });
    api.exportVersion.mockResolvedValue(verifiedExport);
    api.getExport.mockResolvedValue(verifiedExport);
    api.createDownloadIntent.mockResolvedValue({
      exportId: verifiedExport.export.id,
      expiresAt: "2026-07-19T12:02:00Z",
      method: "GET",
      url: "https://downloads.invalid/resume.pdf",
    });
  });

  it("renders an empty state and creates a grounded resume", async () => {
    render(<ResumeBuilderView />);

    expect(
      await screen.findByRole("heading", { name: "No resumes yet" }),
    ).toBeVisible();
    fireEvent.change(screen.getByLabelText("Resume title"), {
      target: { value: "API Resume" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    expect(
      await screen.findAllByText(
        "Resume created from eligible Career Record evidence.",
      ),
    ).not.toHaveLength(0);
    expect(
      screen.getAllByText(
        "Confirmed product discovery work across customer interviews.",
      )[0],
    ).toBeVisible();
    expect(api.createResume).toHaveBeenCalledWith({
      targetRole: null,
      template: "standard_professional",
      title: "API Resume",
    });
  });

  it("exports a verified resume and creates a download intent", async () => {
    api.listResumes.mockResolvedValue([baseResume]);
    api.listVersions.mockResolvedValue([baseVersion]);
    render(<ResumeBuilderView />);

    expect(
      await screen.findByRole("button", { name: "Recruiter preview" }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));
    expect(await screen.findByText("Fidelity verified")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Download" }));
    expect(
      await screen.findByText("https://downloads.invalid/resume.pdf"),
    ).toBeVisible();
  });

  it("shows blocked verification and keeps download disabled", async () => {
    api.listResumes.mockResolvedValue([baseResume]);
    api.exportVersion.mockResolvedValue({
      ...verifiedExport,
      export: {
        ...verifiedExport.export,
        criticalFailures: ["missing:Experience"],
        status: "blocked",
        verificationStatus: "failed",
      },
      verification: {
        ...verifiedExport.verification!,
        criticalFailures: ["missing:Experience"],
        missingLines: ["Experience"],
        status: "failed",
      },
    });
    render(<ResumeBuilderView />);

    expect(
      await screen.findByRole("button", { name: "Recruiter preview" }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));
    expect(
      await screen.findAllByText(
        "Fidelity verification blocked this export. No download was created.",
      ),
    ).not.toHaveLength(0);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Download" })).toBeDisabled(),
    );
  });

  it("supports structured undo and autosaves the preserved draft", async () => {
    api.listResumes.mockResolvedValue([baseResume]);
    api.listVersions.mockResolvedValue([baseVersion]);
    api.updateResume.mockImplementation(
      async (_resume: Resume, input: { title?: string | null }) => ({
        ...baseResume,
        currentVersion: {
          ...baseVersion,
          title: input.title ?? baseVersion.title,
        },
        title: input.title ?? baseResume.title,
        version: 2,
      }),
    );
    render(<ResumeBuilderView />);

    expect(
      await screen.findByRole("button", { name: "Recruiter preview" }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Section" }));
    expect(screen.getByLabelText("Section 2 title")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Undo edit" }));
    expect(screen.queryByLabelText("Section 2 title")).not.toBeInTheDocument();

    const fields = screen.getByRole("region", {
      name: "Resume fields and layout",
    });
    fireEvent.change(within(fields).getByLabelText("Resume title"), {
      target: { value: "Autosaved resume" },
    });

    await waitFor(
      () =>
        expect(api.updateResume).toHaveBeenCalledWith(
          baseResume,
          expect.objectContaining({ title: "Autosaved resume" }),
        ),
      { timeout: 2_000 },
    );
    expect((await screen.findAllByText("All changes saved"))[0]).toBeVisible();
  });

  it("serializes autosaves and preserves edits made during an in-flight save", async () => {
    const firstSave = deferred<Resume>();
    const firstUpdated: Resume = {
      ...baseResume,
      currentVersion: {
        ...baseVersion,
        title: "First edit",
      },
      title: "First edit",
      version: 2,
    };
    api.listResumes.mockResolvedValue([baseResume]);
    api.listVersions.mockResolvedValue([baseVersion]);
    api.updateResume
      .mockImplementationOnce(() => firstSave.promise)
      .mockImplementationOnce(
        async (
          resume: Resume,
          input: {
            title?: string | null;
          },
        ) => ({
          ...resume,
          currentVersion: {
            ...resume.currentVersion,
            title: input.title ?? resume.currentVersion.title,
          },
          title: input.title ?? resume.title,
          version: resume.version + 1,
        }),
      );
    render(<ResumeBuilderView />);

    expect(
      await screen.findByRole("button", { name: "Recruiter preview" }),
    ).toBeVisible();
    const fields = screen.getByRole("region", {
      name: "Resume fields and layout",
    });
    const title = within(fields).getByLabelText("Resume title");
    fireEvent.change(title, { target: { value: "First edit" } });
    await waitFor(() => expect(api.updateResume).toHaveBeenCalledTimes(1), {
      timeout: 2_000,
    });

    fireEvent.change(title, { target: { value: "Latest edit" } });
    await new Promise((resolve) => setTimeout(resolve, 900));
    expect(api.updateResume).toHaveBeenCalledTimes(1);

    firstSave.resolve(firstUpdated);
    await waitFor(() => expect(api.updateResume).toHaveBeenCalledTimes(2), {
      timeout: 2_000,
    });
    expect(api.updateResume).toHaveBeenLastCalledWith(
      expect.objectContaining({ version: 2 }),
      expect.objectContaining({ title: "Latest edit" }),
    );
    expect((await screen.findAllByText("All changes saved"))[0]).toBeVisible();
  });

  it("does not apply a late restore response after another resume is selected", async () => {
    const historicalVersion: ResumeVersion = {
      ...baseVersion,
      id: "00000000-0000-4000-8000-000000000809",
      title: "Historical API Resume",
      versionNumber: 0,
    };
    const otherVersion: ResumeVersion = {
      ...baseVersion,
      id: "00000000-0000-4000-8000-000000000811",
      plainText: "Second Resume\nPlatform Lead",
      resumeId: "00000000-0000-4000-8000-000000000812",
      targetRole: "Platform Lead",
      title: "Second Resume",
    };
    const otherResume: Resume = {
      ...baseResume,
      currentVersion: otherVersion,
      currentVersionId: otherVersion.id,
      id: otherVersion.resumeId,
      targetRole: otherVersion.targetRole,
      title: otherVersion.title,
    };
    const restoredVersion: ResumeVersion = {
      ...historicalVersion,
      versionNumber: 2,
    };
    const restoredResume: Resume = {
      ...baseResume,
      currentVersion: restoredVersion,
      currentVersionId: restoredVersion.id,
      title: restoredVersion.title,
      version: 2,
    };
    const pendingRestore = deferred<Resume>();
    api.listResumes.mockResolvedValue([baseResume, otherResume]);
    api.listVersions.mockImplementation(async (resumeId: string) =>
      resumeId === baseResume.id
        ? [baseVersion, historicalVersion]
        : [otherVersion],
    );
    api.restoreVersion.mockImplementation(() => pendingRestore.promise);
    render(<ResumeBuilderView />);

    const restore = await screen.findByRole("button", {
      name: "Restore version 0",
    });
    fireEvent.click(restore);
    await waitFor(() => expect(api.restoreVersion).toHaveBeenCalledTimes(1));

    const selector = screen.getByRole("combobox", { name: "Resume" });
    fireEvent.change(selector, { target: { value: otherResume.id } });
    const fields = screen.getByRole("region", {
      name: "Resume fields and layout",
    });
    expect(within(fields).getByLabelText("Resume title")).toHaveValue(
      "Second Resume",
    );

    pendingRestore.resolve(restoredResume);
    await waitFor(() =>
      expect(within(fields).getByLabelText("Resume title")).toHaveValue(
        "Second Resume",
      ),
    );
    expect(selector).toHaveValue(otherResume.id);
  });

  it("does not show a late export result for a newly selected resume", async () => {
    const otherVersion: ResumeVersion = {
      ...baseVersion,
      id: "00000000-0000-4000-8000-000000000821",
      plainText: "Second Resume\nPlatform Lead",
      resumeId: "00000000-0000-4000-8000-000000000822",
      targetRole: "Platform Lead",
      title: "Second Resume",
    };
    const otherResume: Resume = {
      ...baseResume,
      currentVersion: otherVersion,
      currentVersionId: otherVersion.id,
      id: otherVersion.resumeId,
      targetRole: otherVersion.targetRole,
      title: otherVersion.title,
    };
    const pendingExport = deferred<ResumeExportRecord>();
    api.listResumes.mockResolvedValue([baseResume, otherResume]);
    api.listVersions.mockImplementation(async (resumeId: string) =>
      resumeId === baseResume.id ? [baseVersion] : [otherVersion],
    );
    api.exportVersion.mockImplementation(() => pendingExport.promise);
    render(<ResumeBuilderView />);

    const verify = await screen.findByRole("button", { name: "Verify" });
    fireEvent.click(verify);
    await waitFor(() => expect(api.exportVersion).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByRole("combobox", { name: "Resume" }), {
      target: { value: otherResume.id },
    });

    pendingExport.resolve(verifiedExport);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Verify" })).toBeEnabled(),
    );
    const fields = screen.getByRole("region", {
      name: "Resume fields and layout",
    });
    expect(within(fields).getByLabelText("Resume title")).toHaveValue(
      "Second Resume",
    );
    expect(screen.queryByText("Fidelity verified")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Export passed independent fidelity verification."),
    ).not.toBeInTheDocument();
  });

  it("polls a pending export until its durable result is verified", async () => {
    api.listResumes.mockResolvedValue([baseResume]);
    api.exportVersion.mockResolvedValue({
      export: {
        ...verifiedExport.export,
        attempts: 0,
        completedAt: null,
        parserVersion: null,
        rendererVersion: "resume-renderer-unset",
        sha256Digest: null,
        sizeBytes: 0,
        status: "pending",
        verificationCodes: [],
        verificationStatus: null,
      },
      verification: null,
    });
    api.getExport.mockResolvedValue(verifiedExport);
    render(<ResumeBuilderView />);

    expect(
      await screen.findByRole("button", { name: "Recruiter preview" }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));

    expect(await screen.findByText("Fidelity verified")).toBeVisible();
    expect(api.getExport).toHaveBeenCalledWith(verifiedExport.export.id);
  });

  it("confirms and polls durable deletion without removing resume history", async () => {
    api.listResumes.mockResolvedValue([baseResume]);
    api.listVersions.mockResolvedValue([baseVersion]);
    api.getExport.mockResolvedValue({
      ...verifiedExport,
      export: {
        ...verifiedExport.export,
        deletedAt: "2026-07-19T12:03:00Z",
        status: "deleted",
      },
    });
    render(<ResumeBuilderView />);

    expect(
      await screen.findByRole("button", { name: "Recruiter preview" }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));
    expect(await screen.findByText("Fidelity verified")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Delete export" }));
    expect(await screen.findByText("Confirm export deletion")).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Confirm delete export" }),
    );

    expect(
      await screen.findAllByText(
        "Export file deleted. Immutable resume history is unchanged.",
      ),
    ).not.toHaveLength(0);
    expect(screen.getByText("Deleted")).toBeVisible();
    expect(api.deleteExport).toHaveBeenCalledWith(verifiedExport.export.id);
    expect(api.getExport).toHaveBeenCalledWith(verifiedExport.export.id);
    expect(screen.getByText("Version 1", { selector: "p" })).toBeVisible();
  });
});
