import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { EvidenceItem } from "../api/types";
import { EvidenceVaultView } from "../views/evidence-vault-view";

const api = vi.hoisted(() => ({
  getEvidence: vi.fn(),
  getExperiences: vi.fn(),
  getSkills: vi.fn(),
}));

vi.mock("../api/career-vault-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/career-vault-api")>()),
  getEvidence: api.getEvidence,
  getExperiences: api.getExperiences,
  getSkills: api.getSkills,
}));

const item: EvidenceItem = {
  archivedAt: null,
  attachments: [],
  conflicts: [],
  createdAt: "2026-07-15T00:00:00Z",
  description: "A user-entered source note.",
  eligibilityReasons: ["owner_confirmation_required"],
  endDate: null,
  factualEligible: false,
  history: [],
  id: "00000000-0000-4000-8000-000000000501",
  lifecycle: "active",
  metrics: [],
  numericEligible: false,
  organizationOrProject: null,
  provenance: [],
  revision: 1,
  startDate: null,
  state: "inferred",
  title: "Fictional source note",
  type: "user_note",
  updatedAt: "2026-07-15T00:00:00Z",
  usage: [],
  userConfirmed: false,
  version: 1,
};

describe("Evidence Vault states", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getExperiences.mockResolvedValue([]);
    api.getSkills.mockResolvedValue([]);
  });

  it("renders the real empty state without demo metrics", async () => {
    api.getEvidence.mockResolvedValue({
      data: [],
      page: { hasMore: false, limit: 25, nextCursor: null },
    });
    render(<EvidenceVaultView />);

    expect(
      await screen.findByRole("heading", {
        name: "Your Evidence Vault is empty",
      }),
    ).toBeVisible();
    expect(screen.getByText(/A resume is not required/)).toBeVisible();
  });

  it("displays server-authoritative ineligible values", async () => {
    api.getEvidence.mockResolvedValue({
      data: [item],
      page: { hasMore: false, limit: 25, nextCursor: null },
    });
    render(<EvidenceVaultView />);

    expect(
      await screen.findAllByText("Fictional source note"),
    ).not.toHaveLength(0);
    expect(screen.getAllByText("Not eligible")).toHaveLength(4);
  });

  it("renders a retryable failure state", async () => {
    api.getEvidence.mockRejectedValue(new Error("offline"));
    render(<EvidenceVaultView />);

    expect(
      await screen.findByRole("heading", {
        name: "Evidence Vault unavailable",
      }),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();
  });
});
