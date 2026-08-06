import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Role, RoleReadiness, SavedRole } from "../api/types";
import { RoleExplorerView } from "../views/role-explorer-view";

const api = vi.hoisted(() => ({
  analyzeRole: vi.fn(),
  compareRoles: vi.fn(),
  deleteSavedRole: vi.fn(),
  getReadinessHistory: vi.fn(),
  getRoles: vi.fn(),
  getSavedRoles: vi.fn(),
  saveRole: vi.fn(),
  updateSavedRole: vi.fn(),
}));

vi.mock("../api/role-explorer-api", () => api);

const role: Role = {
  companyType: "software",
  competencies: [
    {
      adjacentKeywords: ["coordination"],
      description: "Evidence of user research.",
      dimension: "core_competency",
      evidenceKeywords: ["research"],
      id: "00000000-0000-4000-8000-000000000501",
      importance: "required",
      label: "Customer discovery",
      order: 10,
      skillKeywords: ["user research"],
      transferableKeywords: ["planning"],
    },
  ],
  description: "Owns discovery and measurable outcomes.",
  domain: "Product",
  id: "00000000-0000-4000-8000-000000000411",
  industry: "Technology",
  locationScope: "global",
  seniority: "senior",
  slug: "product-manager",
  taxonomy: {
    description: "Seed taxonomy.",
    id: "00000000-0000-4000-8000-000000000401",
    publishedAt: "2026-07-19T00:00:00Z",
    sourceLicense: "Rezumi internal product taxonomy",
    sourceName: "Rezumi authored seed taxonomy",
    version: "rezumi-seed-roles/2026-07-19",
  },
  title: "Product Manager",
  version: 1,
};

const savedRole: SavedRole = {
  createdAt: "2026-07-19T12:00:00Z",
  id: "00000000-0000-4000-8000-000000000901",
  notes: "Primary target",
  role,
  updatedAt: "2026-07-19T12:00:00Z",
  version: 1,
};

const analysis: RoleReadiness = {
  components: [
    {
      contributionBasisPoints: 900,
      dimension: "core_competency",
      explanation: "Coverage of role-defining competencies.",
      scoreBasisPoints: 9000,
      weightBasisPoints: 1000,
    },
  ],
  competencies: [
    {
      competencyId: role.competencies[0]!.id,
      dimension: "core_competency",
      evidence: [
        {
          evidenceId: "00000000-0000-4000-8000-000000000801",
          evidenceStrength: "confirmed",
          evidenceTitle: "Confirmed customer discovery",
          id: "00000000-0000-4000-8000-000000000802",
          rationale: "Eligible evidence directly matches this competency.",
          relevanceBasisPoints: 10000,
        },
      ],
      explanation: "Eligible evidence demonstrates this competency.",
      gapKind: null,
      id: "00000000-0000-4000-8000-000000000701",
      importance: "required",
      label: "Customer discovery",
      matchState: "demonstrated",
      scoreBasisPoints: 10000,
    },
  ],
  configurationVersion: "role-readiness-default/1",
  createdAt: "2026-07-19T12:00:00Z",
  displayScore: 78,
  engineVersion: "role-readiness/1.0.0",
  featureSchemaVersion: "role-readiness-features/1",
  id: "00000000-0000-4000-8000-000000000601",
  insufficientReason: null,
  rawScoreBasisPoints: 7800,
  readinessLabel: "developing",
  role,
  savedRoleId: savedRole.id,
  scoringDisclaimer:
    "Rezumi scores are internal readiness measurements. They are not scores provided by an employer or applicant tracking system and do not guarantee interviews or employment outcomes.",
  summary:
    "Product Manager readiness is based on 1 demonstrated competency and 0 gaps.",
  taxonomyVersion: "rezumi-seed-roles/2026-07-19",
};

describe("Role Explorer view", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getRoles.mockResolvedValue({
      data: [role],
      page: { hasMore: false, limit: 30, nextCursor: null },
    });
    api.getSavedRoles.mockResolvedValue({
      data: [],
      page: { hasMore: false, limit: 25, nextCursor: null },
    });
    api.getReadinessHistory.mockResolvedValue({
      data: [],
      page: { hasMore: false, limit: 25, nextCursor: null },
    });
    api.saveRole.mockResolvedValue(savedRole);
    api.analyzeRole.mockResolvedValue(analysis);
  });

  it("renders empty saved-role and readiness states without demo data", async () => {
    render(<RoleExplorerView />);

    expect(
      await screen.findByRole("heading", { name: "Matching roles" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "No saved roles" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "No readiness analysis" }),
    ).toBeVisible();
    expect(screen.queryByText(/ATS score/i)).not.toBeInTheDocument();
  });

  it("saves and analyzes a real role target", async () => {
    render(<RoleExplorerView />);

    fireEvent.click(await screen.findByRole("button", { name: "Save" }));
    expect(
      await screen.findAllByText("Product Manager saved."),
    ).not.toHaveLength(0);
    expect(api.saveRole).toHaveBeenCalledWith({ notes: null, roleId: role.id });

    fireEvent.click(screen.getAllByRole("button", { name: "Analyze" })[0]!);
    expect(await screen.findAllByText("78/100")).not.toHaveLength(0);
    expect(screen.getByText("Confirmed customer discovery")).toBeVisible();
    expect(screen.getByText(analysis.scoringDisclaimer)).toBeVisible();
    expect(api.analyzeRole).toHaveBeenCalledWith({ roleId: role.id });
  });

  it("renders a retryable failure state", async () => {
    api.getRoles.mockRejectedValue(new Error("offline"));
    render(<RoleExplorerView />);

    expect(
      await screen.findByRole("heading", { name: "Role Explorer unavailable" }),
    ).toBeVisible();
  });
});
