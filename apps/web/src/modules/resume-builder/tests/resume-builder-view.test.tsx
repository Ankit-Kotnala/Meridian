import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Resume, ResumeExportRecord, ResumeVersion } from "../api/types";
import { ResumeBuilderView } from "../views/resume-builder-view";

const api = vi.hoisted(() => ({
  createDownloadIntent: vi.fn(),
  createResume: vi.fn(),
  createVersion: vi.fn(),
  exportVersion: vi.fn(),
  listResumes: vi.fn(),
  listVersions: vi.fn(),
  restoreVersion: vi.fn(),
  updateResume: vi.fn(),
  waitForExportCompletion: vi.fn(),
}));

vi.mock("../api/resume-builder-api", () => api);

const baseVersion: ResumeVersion = {
  createdAt: "2026-07-19T12:00:00Z",
  id: "00000000-0000-4000-8000-000000000801",
  parentVersionId: null,
  plainText:
    "API Resume\nSenior Product Manager\nExperience\nConfirmed product discovery work across customer interviews.",
  resumeId: "00000000-0000-4000-8000-000000000802",
  sections: [
    {
      id: "00000000-0000-4000-8000-000000000803",
      items: [
        {
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
  targetRole: "Senior Product Manager",
  template: "standard_professional",
  title: "API Resume",
  updatedAt: "2026-07-19T12:00:00Z",
  version: 1,
};

const verifiedExport: ResumeExportRecord = {
  export: {
    completedAt: "2026-07-19T12:00:01Z",
    criticalFailures: [],
    deletedAt: null,
    format: "pdf",
    id: "00000000-0000-4000-8000-000000000806",
    mediaType: "application/pdf",
    parserVersion: "test-parser",
    rendererVersion: "test-renderer",
    requestedAt: "2026-07-19T12:00:00Z",
    resumeId: baseResume.id,
    sha256Digest: "a".repeat(64),
    sizeBytes: 1024,
    status: "verified",
    verificationCodes: ["round_trip_searchable"],
    verificationStatus: "passed",
    versionId: baseVersion.id,
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
    missingLines: [],
    parserVersion: "test-parser",
    readingOrder: ["API Resume"],
    status: "passed",
    versionId: baseVersion.id,
    warnings: [],
  },
};

describe("Resume Builder view", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listResumes.mockResolvedValue([]);
    api.listVersions.mockResolvedValue([]);
    api.createResume.mockResolvedValue(baseResume);
    api.updateResume.mockResolvedValue({ ...baseResume, version: 2 });
    api.createVersion.mockResolvedValue({ ...baseVersion, versionNumber: 2 });
    api.exportVersion.mockResolvedValue(verifiedExport);
    api.waitForExportCompletion.mockImplementation(async (record) => record);
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
      screen.getByText(
        "Confirmed product discovery work across customer interviews.",
      ),
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

    expect(await screen.findByText("Recruiter preview")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));
    expect(await screen.findByText("Round-trip verified")).toBeVisible();
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

    expect(await screen.findByText("Recruiter preview")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));
    expect(
      await screen.findAllByText(
        "Round-trip verification blocked this export.",
      ),
    ).not.toHaveLength(0);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Download" })).toBeDisabled(),
    );
  });

  it("waits for a pending durable export before enabling download", async () => {
    api.listResumes.mockResolvedValue([baseResume]);
    api.exportVersion.mockResolvedValue({
      export: {
        ...verifiedExport.export,
        completedAt: null,
        parserVersion: null,
        sha256Digest: null,
        sizeBytes: 0,
        status: "pending",
        verificationCodes: [],
        verificationStatus: null,
      },
      verification: null,
    });
    api.waitForExportCompletion.mockResolvedValue(verifiedExport);
    render(<ResumeBuilderView />);

    expect(await screen.findByText("Recruiter preview")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));
    expect(await screen.findByText("Round-trip verified")).toBeVisible();
    expect(api.waitForExportCompletion).toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Download" })).toBeEnabled();
  });
});
