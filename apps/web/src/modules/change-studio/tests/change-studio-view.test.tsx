import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ChangeSet } from "../api/types";
import { ChangeStudioView } from "../views/change-studio-view";

const api = vi.hoisted(() => ({
  acceptOperation: vi.fn(),
  answerClarification: vi.fn(),
  applySafeChanges: vi.fn(),
  createAlternative: vi.fn(),
  createChangeSet: vi.fn(),
  editOperation: vi.fn(),
  getChangeSet: vi.fn(),
  redoChangeSet: vi.fn(),
  rejectOperation: vi.fn(),
  restoreVersion: vi.fn(),
  setOperationLocked: vi.fn(),
  undoChangeSet: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("analysisId=analysis-1"),
}));

vi.mock("../api/change-studio-api", () => api);

const disclaimer =
  "CareerOS scores are internal readiness measurements. They are not scores provided by an employer or applicant tracking system and do not guarantee interviews or employment outcomes.";

const baseChangeSet: ChangeSet = {
  analysisId: "00000000-0000-4000-8000-000000000604",
  createdAt: "2026-07-19T12:00:00Z",
  currentVersion: {
    content: "",
    createdAt: "2026-07-19T12:00:00Z",
    createdByOperationId: null,
    id: "00000000-0000-4000-8000-000000000701",
    operationIds: [],
    parentVersionId: null,
    title: "Baseline for Product Manager",
    versionNumber: 1,
  },
  currentVersionId: "00000000-0000-4000-8000-000000000701",
  groundingVersion: "change-studio-grounding/1.0.0",
  id: "00000000-0000-4000-8000-000000000702",
  jobId: "00000000-0000-4000-8000-000000000603",
  operations: [
    {
      afterText:
        "Confirmed evidence for user research, customer discovery, and product experiments.",
      beforeText: "",
      claims: [
        {
          claimKind: "skill",
          createdAt: "2026-07-19T12:00:00Z",
          evidenceId: "00000000-0000-4000-8000-000000000608",
          evidenceRevisionId: "00000000-0000-4000-8000-000000000609",
          evidenceRevisionNumber: 1,
          evidenceStatementSha256: "c".repeat(64),
          evidenceStrength: "confirmed",
          evidenceTitle: "Confirmed discovery program",
          id: "00000000-0000-4000-8000-000000000703",
          sortOrder: 10,
          sourceExcerpt:
            "Confirmed evidence for user research, customer discovery, and product experiments.",
          text: "Confirmed evidence for user research, customer discovery, and product experiments.",
          validationCodes: ["grounded"],
          validationStatus: "passed",
        },
      ],
      confidenceBasisPoints: 9200,
      createdAt: "2026-07-19T12:00:00Z",
      expectedScoreDeltaBasisPoints: 150,
      groundingCodes: ["grounded"],
      groundingStatus: "grounded",
      id: "00000000-0000-4000-8000-000000000704",
      locked: false,
      operationType: "add_bullet",
      reason: "Uses eligible Career Record evidence.",
      requirementId: "00000000-0000-4000-8000-000000000606",
      requirementText:
        "Must have experience with user research and product experiments.",
      requiresConfirmation: true,
      risk: "low",
      sortOrder: 10,
      status: "proposed",
      targetId: "00000000-0000-4000-8000-000000000606",
      targetKind: "tailored_resume_bullet",
      updatedAt: "2026-07-19T12:00:00Z",
      version: 1,
    },
  ],
  policyVersion: "ai-grounding-policy/2026-07-14",
  promptVersion: "change-studio-prompt/1",
  providerModel: "change-studio-fake/1",
  providerName: "deterministic-local",
  providerRuns: [],
  purpose: "job_tailoring",
  questions: [
    {
      answerText: null,
      answeredAt: null,
      createdAt: "2026-07-19T12:00:00Z",
      evidenceId: null,
      id: "00000000-0000-4000-8000-000000000705",
      operationId: null,
      question:
        "What evidence can support this requirement: Preferred billing systems.",
      reason: "No currently eligible evidence can ground a resume change.",
      requirementId: "00000000-0000-4000-8000-000000000607",
      status: "open",
      updatedAt: "2026-07-19T12:00:00Z",
    },
  ],
  schemaVersion: "change-studio-provider-output/1",
  scoringDisclaimer: disclaimer,
  status: "draft",
  targetKind: "tailored_resume_bullet",
  updatedAt: "2026-07-19T12:00:00Z",
  version: 1,
  versions: [
    {
      content: "",
      createdAt: "2026-07-19T12:00:00Z",
      createdByOperationId: null,
      id: "00000000-0000-4000-8000-000000000701",
      operationIds: [],
      parentVersionId: null,
      title: "Baseline for Product Manager",
      versionNumber: 1,
    },
  ],
};

const acceptedChangeSet: ChangeSet = {
  ...baseChangeSet,
  currentVersion: {
    content: baseChangeSet.operations[0]!.afterText,
    createdAt: "2026-07-19T12:01:00Z",
    createdByOperationId: baseChangeSet.operations[0]!.id,
    id: "00000000-0000-4000-8000-000000000801",
    operationIds: [baseChangeSet.operations[0]!.id],
    parentVersionId: baseChangeSet.currentVersionId,
    title: "Accepted change 1",
    versionNumber: 2,
  },
  currentVersionId: "00000000-0000-4000-8000-000000000801",
  operations: [{ ...baseChangeSet.operations[0]!, status: "accepted" }],
  version: 2,
  versions: [
    ...baseChangeSet.versions,
    {
      content: baseChangeSet.operations[0]!.afterText,
      createdAt: "2026-07-19T12:01:00Z",
      createdByOperationId: baseChangeSet.operations[0]!.id,
      id: "00000000-0000-4000-8000-000000000801",
      operationIds: [baseChangeSet.operations[0]!.id],
      parentVersionId: baseChangeSet.currentVersionId,
      title: "Accepted change 1",
      versionNumber: 2,
    },
  ],
};

describe("Change Studio view", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.createChangeSet.mockResolvedValue(baseChangeSet);
    api.acceptOperation.mockResolvedValue(acceptedChangeSet);
    api.undoChangeSet.mockResolvedValue(baseChangeSet);
    api.answerClarification.mockResolvedValue({
      ...baseChangeSet,
      questions: [
        {
          ...baseChangeSet.questions[0]!,
          answerText: "I do not have that evidence yet.",
          status: "answered",
        },
      ],
      version: 2,
    });
  });

  it("renders the empty state without demo suggestions", () => {
    render(<ChangeStudioView />);

    expect(
      screen.getByRole("heading", { name: "No change set loaded" }),
    ).toBeVisible();
    expect(screen.queryByText(/demo/i)).not.toBeInTheDocument();
  });

  it("generates suggestions, accepts one, and answers a clarification", async () => {
    render(<ChangeStudioView />);

    fireEvent.click(screen.getByRole("button", { name: "Generate" }));
    expect(
      await screen.findAllByText("Grounded suggestions are ready for review."),
    ).not.toHaveLength(0);
    expect(screen.getByText("Confirmed discovery program")).toBeVisible();
    expect(screen.getByText(disclaimer)).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Accept" }));
    expect(await screen.findAllByText("Suggestion accepted.")).not.toHaveLength(
      0,
    );
    expect(
      screen.getAllByText(
        "Confirmed evidence for user research, customer discovery, and product experiments.",
      ),
    ).not.toHaveLength(0);

    fireEvent.change(screen.getByLabelText("Answer"), {
      target: { value: "I do not have that evidence yet." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save answer" }));
    expect(await screen.findAllByText("Answer saved.")).not.toHaveLength(0);
    expect(api.answerClarification).toHaveBeenCalledWith(
      acceptedChangeSet,
      baseChangeSet.questions[0]!.id,
      { answerText: "I do not have that evidence yet." },
    );
  });

  it("renders provider failures as an error state", async () => {
    api.createChangeSet.mockRejectedValue(new Error("grounding unavailable"));
    render(<ChangeStudioView />);

    fireEvent.click(screen.getByRole("button", { name: "Generate" }));
    expect(
      await screen.findAllByText(
        "Change Studio could not generate suggestions.",
      ),
    ).not.toHaveLength(0);
  });
});
