import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getDocument: vi.fn(),
  getPlainText: vi.fn(),
  getReadingOrder: vi.fn(),
  startResumeHealth: vi.fn(),
  updateCanonicalResume: vi.fn(),
}));
const push = vi.fn();

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("../api/resume-health-api", () => ({
  ...api,
  ApiRequestError: class extends Error {},
  newIdempotencyKey: () => "00000000-0000-4000-8000-000000000001",
}));

import { CanonicalReviewView } from "../views/canonical-review-view";

const canonical = {
  id: "00000000-0000-4000-8000-000000000003",
  documentId: "00000000-0000-4000-8000-000000000002",
  schemaVersion: "canonical-resume/1",
  version: 1,
  sections: [
    {
      id: "00000000-0000-4000-8000-000000000004",
      kind: "summary",
      title: "Summary",
      fields: [
        {
          id: "00000000-0000-4000-8000-000000000005",
          label: "Summary",
          value: "Original fictional summary",
          originalValue: "Original fictional summary",
          confidence: 55,
          sourceSpans: [
            {
              page: 1,
              start: 0,
              end: 28,
              excerpt: "Original fictional summary",
            },
          ],
        },
      ],
    },
  ],
  warnings: [
    {
      code: "low_parser_confidence",
      message: "Review this field.",
      fieldId: null,
    },
  ],
  correctedByUser: false,
  createdAt: "2026-07-15T00:00:00Z",
} as const;

describe("canonical resume review", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("preserves the extracted source while saving an explicit correction", async () => {
    api.getDocument.mockResolvedValue({
      id: canonical.documentId,
      displayFilename: "fictional.pdf",
      mediaType: "application/pdf",
      sizeBytes: 500,
      status: "reviewReady",
      version: 1,
      currentCanonicalResumeId: canonical.id,
      latestAnalysisId: null,
      createdAt: "2026-07-15T00:00:00Z",
      updatedAt: "2026-07-15T00:00:00Z",
      expiresAt: null,
      canonicalResume: canonical,
    });
    api.getPlainText.mockResolvedValue({
      documentId: canonical.documentId,
      text: "Original fictional summary",
      truncated: false,
    });
    api.getReadingOrder.mockResolvedValue({
      documentId: canonical.documentId,
      blocks: [{ index: 0, page: 1, text: "Original fictional summary" }],
    });
    api.updateCanonicalResume.mockResolvedValue({
      ...canonical,
      version: 2,
      correctedByUser: true,
    });
    api.startResumeHealth.mockResolvedValue({
      job: {
        id: "00000000-0000-4000-8000-000000000009",
      },
    });
    render(
      <CanonicalReviewView
        access="account"
        documentId={canonical.documentId}
      />,
    );

    const input = await screen.findByLabelText("Reviewed Summary");
    expect(
      screen.getAllByText("Original fictional summary").length,
    ).toBeGreaterThan(0);
    fireEvent.change(input, {
      target: { value: "Corrected fictional summary" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Save review and analyze" }),
    );

    await waitFor(() =>
      expect(api.updateCanonicalResume).toHaveBeenCalledOnce(),
    );
    expect(api.updateCanonicalResume).toHaveBeenCalledWith(
      "account",
      canonical.documentId,
      1,
      {
        fields: [
          {
            id: "00000000-0000-4000-8000-000000000005",
            value: "Corrected fictional summary",
          },
        ],
      },
    );
    await waitFor(() =>
      expect(push).toHaveBeenCalledWith(
        "/resume-health/account/processing/00000000-0000-4000-8000-000000000009",
      ),
    );
  });

  it("starts analysis without submitting a no-op canonical correction", async () => {
    api.getDocument.mockResolvedValue({
      id: canonical.documentId,
      displayFilename: "fictional.pdf",
      mediaType: "application/pdf",
      sizeBytes: 500,
      status: "reviewReady",
      version: 1,
      currentCanonicalResumeId: canonical.id,
      latestAnalysisId: null,
      createdAt: "2026-07-15T00:00:00Z",
      updatedAt: "2026-07-15T00:00:00Z",
      expiresAt: null,
      canonicalResume: canonical,
    });
    api.getPlainText.mockResolvedValue({
      documentId: canonical.documentId,
      text: "Original fictional summary",
      truncated: false,
    });
    api.getReadingOrder.mockResolvedValue({
      documentId: canonical.documentId,
      blocks: [{ index: 0, page: 1, text: "Original fictional summary" }],
    });
    api.startResumeHealth.mockResolvedValue({
      job: { id: "00000000-0000-4000-8000-000000000010" },
    });

    render(
      <CanonicalReviewView access="guest" documentId={canonical.documentId} />,
    );
    fireEvent.click(
      await screen.findByRole("button", {
        name: "Save review and analyze",
      }),
    );

    await waitFor(() => expect(api.startResumeHealth).toHaveBeenCalledOnce());
    expect(api.updateCanonicalResume).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(push).toHaveBeenCalledWith(
        "/resume-health/guest/processing/00000000-0000-4000-8000-000000000010",
      ),
    );
  });

  it("acknowledges image-only extraction and starts an insufficient-data analysis", async () => {
    const imageOnlyCanonical = {
      ...canonical,
      sections: [],
      warnings: [
        {
          code: "image_only_pdf",
          message: "No searchable text was found.",
          fieldId: null,
        },
      ],
    };
    api.getDocument.mockResolvedValue({
      id: canonical.documentId,
      displayFilename: "image-only.pdf",
      mediaType: "application/pdf",
      sizeBytes: 500,
      status: "reviewReady",
      version: 1,
      currentCanonicalResumeId: canonical.id,
      latestAnalysisId: null,
      createdAt: "2026-07-15T00:00:00Z",
      updatedAt: "2026-07-15T00:00:00Z",
      expiresAt: null,
      canonicalResume: imageOnlyCanonical,
    });
    api.getPlainText.mockResolvedValue({
      documentId: canonical.documentId,
      text: "",
      truncated: false,
    });
    api.getReadingOrder.mockResolvedValue({
      documentId: canonical.documentId,
      blocks: [],
    });
    api.startResumeHealth.mockResolvedValue({
      job: { id: "00000000-0000-4000-8000-000000000011" },
    });

    render(
      <CanonicalReviewView access="guest" documentId={canonical.documentId} />,
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Acknowledge and analyze" }),
    );

    await waitFor(() => expect(api.startResumeHealth).toHaveBeenCalledOnce());
    expect(api.updateCanonicalResume).not.toHaveBeenCalled();
    expect(api.startResumeHealth).toHaveBeenCalledWith(
      "guest",
      canonical.documentId,
      "00000000-0000-4000-8000-000000000001",
    );
    await waitFor(() =>
      expect(push).toHaveBeenCalledWith(
        "/resume-health/guest/processing/00000000-0000-4000-8000-000000000011",
      ),
    );
  });
});
