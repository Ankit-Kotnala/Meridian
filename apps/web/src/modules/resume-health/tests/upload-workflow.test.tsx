import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  createUploadIntent: vi.fn(),
  finalizeUpload: vi.fn(),
  getUploadPolicy: vi.fn(),
  uploadFile: vi.fn(),
}));

vi.mock("../api/resume-health-api", () => ({
  ...api,
  newIdempotencyKey: () => "00000000-0000-4000-8000-000000000001",
}));

import { UploadWorkflow } from "../components/upload-workflow";

const job = {
  id: "00000000-0000-4000-8000-000000000020",
  documentId: "00000000-0000-4000-8000-000000000010",
  jobType: "parse",
  status: "queued",
  stage: "queued",
  progress: null,
  attempts: 0,
  resultType: null,
  resultId: null,
  resultUrl: null,
  error: null,
  createdAt: "2026-07-15T00:00:00Z",
  updatedAt: "2026-07-15T00:00:00Z",
} as const;

const intent = {
  uploadId: "00000000-0000-4000-8000-000000000005",
  url: "http://localhost:9000/private-object",
  method: "PUT",
  headers: { "content-type": "application/pdf" },
  expiresAt: "2099-07-15T00:05:00Z",
  guestExpiresAt: null,
} as const;

function selectResume() {
  const file = new File(["fictional resume"], "fictional.pdf", {
    type: "application/pdf",
  });
  fireEvent.change(screen.getByLabelText("Resume file"), {
    target: { files: [file] },
  });
  return file;
}

describe("resume upload workflow", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    api.getUploadPolicy.mockResolvedValue({
      acceptedMediaTypes: ["application/pdf"],
      maxBytes: 10_000,
      maxPages: 10,
      guestRetentionHours: 24,
      uploadIntentTtlSeconds: 300,
    });
    api.createUploadIntent.mockResolvedValue(intent);
    api.uploadFile.mockResolvedValue(undefined);
    api.finalizeUpload.mockResolvedValue({ documentId: job.documentId, job });
  });

  it("uses the real intent, byte transfer, and finalize sequence", async () => {
    api.uploadFile.mockImplementation(
      async (_intent, _file, progress: (value: number) => void) => {
        progress(50);
        progress(100);
      },
    );
    const onComplete = vi.fn();
    render(<UploadWorkflow access="account" onComplete={onComplete} />);

    await screen.findByLabelText("Resume file");
    const file = selectResume();
    fireEvent.click(screen.getByRole("button", { name: "Upload and review" }));

    await waitFor(() => expect(onComplete).toHaveBeenCalledOnce());
    expect(api.createUploadIntent).toHaveBeenCalledWith(
      "account",
      expect.objectContaining({
        displayFilename: "fictional.pdf",
        expectedSizeBytes: file.size,
      }),
    );
    expect(api.uploadFile).toHaveBeenCalledOnce();
    expect(api.finalizeUpload).toHaveBeenCalledWith(
      "account",
      "00000000-0000-4000-8000-000000000005",
      expect.any(String),
    );
  });

  it("describes PDF and DOCX limits without claiming DOCX page enforcement", async () => {
    api.getUploadPolicy.mockResolvedValueOnce({
      acceptedMediaTypes: [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      ],
      maxBytes: 10_000,
      maxPages: 10,
      guestRetentionHours: 24,
      uploadIntentTtlSeconds: 300,
    });

    render(<UploadWorkflow access="account" onComplete={vi.fn()} />);

    expect(
      await screen.findByText(/PDFs are limited to 10 pages\./),
    ).toHaveTextContent(
      "DOCX files are bounded by archive and extracted-content safety limits.",
    );
    expect(screen.queryByText(/DOCX.*10 pages/i)).not.toBeInTheDocument();
  });

  it("shows policy failures without offering a fake upload", async () => {
    api.getUploadPolicy.mockRejectedValueOnce(new Error("offline"));
    render(<UploadWorkflow access="guest" onComplete={vi.fn()} />);
    expect(
      await screen.findByRole("heading", { name: "Secure upload unavailable" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Upload and review" }),
    ).not.toBeInTheDocument();
  });

  it("reuses an issued intent when the byte transfer is retried", async () => {
    api.uploadFile
      .mockRejectedValueOnce(new Error("temporary transfer failure"))
      .mockResolvedValueOnce(undefined);
    const onComplete = vi.fn();
    render(<UploadWorkflow access="guest" onComplete={onComplete} />);
    await screen.findByLabelText("Resume file");
    selectResume();

    fireEvent.click(screen.getByRole("button", { name: "Upload and review" }));
    expect(await screen.findByText("temporary transfer failure")).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Retry upload and review" }),
    );

    await waitFor(() => expect(onComplete).toHaveBeenCalledOnce());
    expect(api.createUploadIntent).toHaveBeenCalledOnce();
    expect(api.uploadFile).toHaveBeenCalledTimes(2);
    expect(api.finalizeUpload).toHaveBeenCalledOnce();
  });

  it("replays finalize with one key after an ambiguous response loss", async () => {
    api.finalizeUpload
      .mockRejectedValueOnce(new Error("completion response lost"))
      .mockResolvedValueOnce({ documentId: job.documentId, job });
    const onComplete = vi.fn();
    render(<UploadWorkflow access="account" onComplete={onComplete} />);
    await screen.findByLabelText("Resume file");
    selectResume();

    fireEvent.click(screen.getByRole("button", { name: "Upload and review" }));
    expect(await screen.findByText("completion response lost")).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Retry upload and review" }),
    );

    await waitFor(() => expect(onComplete).toHaveBeenCalledOnce());
    expect(api.createUploadIntent).toHaveBeenCalledOnce();
    expect(api.uploadFile).toHaveBeenCalledOnce();
    expect(api.finalizeUpload).toHaveBeenCalledTimes(2);
    expect(api.finalizeUpload.mock.calls[0]?.[2]).toBe(
      api.finalizeUpload.mock.calls[1]?.[2],
    );
  });
});
