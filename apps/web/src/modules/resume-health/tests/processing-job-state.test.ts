import { describe, expect, it } from "vitest";

import { isProcessingJobTerminal } from "../hooks/processing-job-state";

describe("processing job terminal state", () => {
  it("keeps polling a failed job while its durable retry is pending", () => {
    expect(
      isProcessingJobTerminal({
        status: "failed",
        error: {
          code: "malware_scanner_timeout",
          message: "Processing could not be completed safely.",
          retryable: true,
        },
      }),
    ).toBe(false);
  });

  it.each(["succeeded", "cancelled", "deadLettered"] as const)(
    "treats %s as terminal",
    (status) => {
      expect(isProcessingJobTerminal({ status, error: null })).toBe(true);
    },
  );

  it("treats a non-retryable failure as terminal", () => {
    expect(
      isProcessingJobTerminal({
        status: "failed",
        error: {
          code: "malware_detected",
          message: "Processing could not be completed safely.",
          retryable: false,
        },
      }),
    ).toBe(true);
  });
});
