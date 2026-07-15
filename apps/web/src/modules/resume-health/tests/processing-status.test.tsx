import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const useProcessingJob = vi.hoisted(() => vi.fn());

vi.mock("../hooks/use-processing-job", () => ({ useProcessingJob }));

import { ProcessingStatus } from "../components/processing-status";

describe("processing status", () => {
  it("does not report durable deletion as complete until the job succeeds", () => {
    useProcessingJob.mockReturnValue({
      failure: undefined,
      retry: vi.fn(),
      job: {
        id: "00000000-0000-4000-8000-000000000040",
        documentId: "00000000-0000-4000-8000-000000000010",
        jobType: "delete",
        status: "running",
        stage: "cleanup",
        progress: 50,
        attempts: 1,
        resultType: null,
        resultId: null,
        resultUrl: null,
        error: null,
        createdAt: "2026-07-15T00:00:00Z",
        updatedAt: "2026-07-15T00:00:01Z",
      },
    });

    const { rerender } = render(
      <ProcessingStatus
        access="account"
        jobId="00000000-0000-4000-8000-000000000040"
        onSucceeded={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "Deleting your resume" }),
    ).toBeVisible();
    expect(screen.queryByText("Private document removed")).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Cancel processing" }),
    ).toBeNull();

    useProcessingJob.mockReturnValue({
      ...useProcessingJob.mock.results[0]?.value,
      job: {
        ...useProcessingJob.mock.results[0]?.value.job,
        status: "succeeded",
        progress: 100,
      },
    });
    rerender(
      <ProcessingStatus
        access="account"
        jobId="00000000-0000-4000-8000-000000000040"
        onSucceeded={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "Resume deletion complete" }),
    ).toBeVisible();
    expect(screen.getByText("Private document removed")).toBeVisible();
  });

  it("presents a retryable failure as waiting, not terminal", () => {
    useProcessingJob.mockReturnValue({
      failure: undefined,
      retry: vi.fn(),
      job: {
        id: "00000000-0000-4000-8000-000000000041",
        documentId: "00000000-0000-4000-8000-000000000010",
        jobType: "parse",
        status: "failed",
        stage: "malwareScan",
        progress: null,
        attempts: 1,
        resultType: null,
        resultId: null,
        resultUrl: null,
        error: {
          code: "malware_scanner_timeout",
          message: "Processing could not be completed safely.",
          retryable: true,
        },
        createdAt: "2026-07-15T00:00:00Z",
        updatedAt: "2026-07-15T00:00:01Z",
      },
    });

    render(
      <ProcessingStatus
        access="account"
        jobId="00000000-0000-4000-8000-000000000041"
        onSucceeded={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Secure processing will retry" }),
    ).toBeVisible();
    expect(screen.getByText("Retry scheduled")).toBeVisible();
    expect(screen.queryByText("Safe processing failure")).toBeNull();
    expect(
      screen.getByRole("button", { name: "Cancel processing" }),
    ).toBeVisible();
  });
});
