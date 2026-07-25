import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  FollowUpDraft,
  InterviewQuestion,
  InterviewSession,
} from "../api/types";
import { InterviewSessionDetailView } from "../views/interview-session-detail-view";

const router = vi.hoisted(() => ({
  refresh: vi.fn(),
  replace: vi.fn(),
}));
const api = vi.hoisted(() => ({
  createQuestion: vi.fn(),
  createSessionNote: vi.fn(),
  deleteSession: vi.fn(),
  deleteSessionNote: vi.fn(),
  generateFollowUpDraft: vi.fn(),
  generateQuestionBank: vi.fn(),
  getSession: vi.fn(),
  listFollowUpDrafts: vi.fn(),
  listQuestions: vi.fn(),
  listSessionNotes: vi.fn(),
  updateSession: vi.fn(),
  updateSessionNote: vi.fn(),
  ApiRequestError: class extends Error {},
}));

vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("../api/interview-prep-api", () => api);

const claimId = "00000000-0000-4000-8000-000000000201";
const session: InterviewSession = {
  applicationId: "00000000-0000-4000-8000-000000000202",
  context: {
    applicationId: "00000000-0000-4000-8000-000000000202",
    claims: [
      {
        evidencePins: [
          {
            evidenceId: "00000000-0000-4000-8000-000000000203",
            evidenceRevisionId: "00000000-0000-4000-8000-000000000204",
            hasNumericClaim: false,
            revisionNumber: 2,
            statement: "Led the deployment hardening work.",
            statementSha256: "b".repeat(64),
            strength: "confirmed",
          },
        ],
        requirementIds: ["00000000-0000-4000-8000-000000000205"],
        sourceClaimId: claimId,
        strong: true,
        text: "Led deployment hardening.",
        textSha256: "a".repeat(64),
      },
    ],
    company: "Example Co",
    jobId: "00000000-0000-4000-8000-000000000206",
    jobTitle: "Principal Engineer",
    jobVersion: 2,
    requirements: [
      {
        importance: "mandatory",
        requirementId: "00000000-0000-4000-8000-000000000205",
        text: "Lead production reliability programs.",
      },
    ],
    resumeVersionId: "00000000-0000-4000-8000-000000000207",
    resumeVersionNumber: 4,
    snapshotSha256: "c".repeat(64),
  },
  createdAt: "2026-07-24T10:00:00Z",
  followUpDraftCount: 0,
  groundingStatus: "current",
  groundingWarning: null,
  id: "00000000-0000-4000-8000-000000000208",
  kind: "behavioral",
  noteCount: 0,
  questionCount: 0,
  questionBankGenerated: false,
  questionBankId: null,
  scheduledAt: "2026-07-25T10:00:00Z",
  title: "Behavioral round",
  updatedAt: "2026-07-24T10:00:00Z",
  version: 1,
};

const question: InterviewQuestion = {
  createdAt: "2026-07-24T10:01:00Z",
  generated: true,
  groundingStatus: "current",
  groundingWarning: null,
  id: "00000000-0000-4000-8000-000000000209",
  kind: "behavioral",
  ordinal: 1,
  prompt: "How did you lead deployment hardening?",
  sessionId: session.id,
  sourceClaimIds: [claimId],
  sourceRequirementIds: [session.context.requirements[0]!.requirementId],
};

const draft: FollowUpDraft = {
  body: "Thank you for discussing production reliability.",
  contentSha256: "d".repeat(64),
  createdAt: "2026-07-24T10:02:00Z",
  groundingStatus: "current",
  groundingWarning: null,
  id: "00000000-0000-4000-8000-000000000210",
  sessionId: session.id,
  sourceClaims: session.context.claims,
  subject: "Thank you",
};

describe("Interview session detail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getSession.mockResolvedValue(session);
    api.listQuestions.mockResolvedValue({
      data: [],
      page: { hasMore: false, limit: 50, nextCursor: null },
    });
    api.listSessionNotes.mockResolvedValue({
      data: [],
      page: { hasMore: false, limit: 50, nextCursor: null },
    });
    api.listFollowUpDrafts.mockResolvedValue({
      data: [],
      page: { hasMore: false, limit: 50, nextCursor: null },
    });
    api.generateQuestionBank.mockResolvedValue({ data: [question] });
    api.generateFollowUpDraft.mockResolvedValue(draft);
  });

  it("generates grounded questions and exposes no send control", async () => {
    render(<InterviewSessionDetailView sessionId={session.id} />);

    expect(
      await screen.findByRole("heading", { name: session.title }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("tab", { name: "Questions (0)" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Generate grounded questions" }),
    );

    expect(await screen.findByText(question.prompt)).toBeVisible();
    expect(api.generateQuestionBank).toHaveBeenCalledWith(
      session.id,
      expect.stringMatching(/^interview-web:/),
    );

    fireEvent.click(screen.getByRole("tab", { name: "Follow-up drafts (0)" }));
    expect(
      screen.getByText(/Draft only — no sending capability/i),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /^send/i }),
    ).not.toBeInTheDocument();
  });

  it("creates a review-only follow-up from selected exact claims", async () => {
    render(<InterviewSessionDetailView sessionId={session.id} />);
    await screen.findByRole("heading", { name: session.title });
    fireEvent.click(screen.getByRole("tab", { name: "Follow-up drafts (0)" }));
    fireEvent.click(
      screen.getAllByLabelText("Led deployment hardening.").at(-1)!,
    );
    fireEvent.click(
      screen.getByRole("button", {
        name: "Create grounded review draft",
      }),
    );

    expect(await screen.findByText(draft.body)).toBeVisible();
    expect(screen.getByText("Not sent")).toBeVisible();
    expect(api.generateFollowUpDraft).toHaveBeenCalledWith(
      session.id,
      { sourceClaimIds: [claimId] },
      expect.stringMatching(/^interview-web:/),
    );
  });
});
