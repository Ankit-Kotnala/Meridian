import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ProfileImportProposal } from "../api/types";
import { AutoImportRunner } from "../components/auto-import-runner";

const api = vi.hoisted(() => ({
  acceptProfileImportProposal: vi.fn(),
  createProfileImportProposals: vi.fn(),
  listProfileImportProposals: vi.fn(),
}));

vi.mock("../api/career-vault-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/career-vault-api")>()),
  acceptProfileImportProposal: api.acceptProfileImportProposal,
  createProfileImportProposals: api.createProfileImportProposals,
  listProfileImportProposals: api.listProfileImportProposals,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}));

const DOCUMENT_ID = "00000000-0000-4000-8000-000000000001";
const SNAPSHOT_ID = "00000000-0000-4000-8000-000000000002";

function proposal(
  overrides: Partial<ProfileImportProposal> = {},
): ProfileImportProposal {
  return {
    changes: [
      {
        conflict: null,
        currentValue: null,
        field: "employer",
        id: "field-1",
        label: "Employer",
        proposedValue: "Fictional Systems",
        reviewState: "confirmed",
        source: {
          available: true,
          confidence: 0.98,
          id: "proposal-1:field-1",
          parserVersion: "1.0.0",
          sourceDocumentId: DOCUMENT_ID,
          sourceLabel: "Confirmed typed resume field",
          sourceRevision: 1,
          sourceSnapshotId: SNAPSHOT_ID,
          sourceType: "resume_semantic",
          spans: [
            {
              digest: "digest-0",
              end: 10,
              excerpt: "Fictional Systems",
              id: "block-1:0",
              page: 1,
              start: 0,
            },
          ],
          userConfirmed: false,
        },
      },
    ],
    createdAt: "2026-08-17T00:00:00Z",
    id: "proposal-1",
    sourceAvailable: true,
    sourceDocumentName: "reviewed resume snapshot 1",
    status: "pending",
    version: 1,
    ...overrides,
  } as ProfileImportProposal;
}

describe("automatic career record import", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.createProfileImportProposals.mockResolvedValue({
      proposals: [],
      questions: [],
    });
    api.listProfileImportProposals.mockResolvedValue([]);
    api.acceptProfileImportProposal.mockImplementation(
      async (candidate: ProfileImportProposal) => candidate,
    );
  });

  it("derives proposals from the reviewed snapshot before applying them", async () => {
    // Nothing else creates proposals, so without this call a reviewed resume
    // never populates the career record and activation never completes.
    api.listProfileImportProposals.mockResolvedValue([proposal()]);

    render(
      <AutoImportRunner documentId={DOCUMENT_ID} snapshotId={SNAPSHOT_ID} />,
    );

    await waitFor(() => {
      expect(api.createProfileImportProposals).toHaveBeenCalledWith(
        DOCUMENT_ID,
        SNAPSHOT_ID,
      );
    });
    await waitFor(() => {
      expect(api.acceptProfileImportProposal).toHaveBeenCalledTimes(1);
    });
    expect(
      await screen.findByText(/added to your career record automatically/i),
    ).toBeInTheDocument();
  });

  it("does not derive proposals when no reviewed snapshot exists yet", async () => {
    render(<AutoImportRunner />);

    await waitFor(() => {
      expect(api.listProfileImportProposals).toHaveBeenCalled();
    });
    expect(api.createProfileImportProposals).not.toHaveBeenCalled();
  });

  it("still applies existing proposals when the snapshot can no longer be derived", async () => {
    api.createProfileImportProposals.mockRejectedValue(
      new Error("source unavailable"),
    );
    api.listProfileImportProposals.mockResolvedValue([proposal()]);

    render(
      <AutoImportRunner documentId={DOCUMENT_ID} snapshotId={SNAPSHOT_ID} />,
    );

    await waitFor(() => {
      expect(api.acceptProfileImportProposal).toHaveBeenCalledTimes(1);
    });
  });

  it("reports entries that were missing a required field instead of inventing one", async () => {
    api.createProfileImportProposals.mockResolvedValue({
      proposals: [],
      questions: [
        { missingFields: ["employer"], semanticEntityId: "entity-1" },
      ],
    });

    render(
      <AutoImportRunner documentId={DOCUMENT_ID} snapshotId={SNAPSHOT_ID} />,
    );

    expect(
      await screen.findByText(/no fact was invented for it/i),
    ).toBeInTheDocument();
  });
});
