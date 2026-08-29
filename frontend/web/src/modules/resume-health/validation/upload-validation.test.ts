import { describe, expect, it } from "vitest";

import type { UploadPolicy } from "../api/types";
import { validateUpload } from "./upload-validation";

const policy = {
  acceptedMediaTypes: [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ],
  maxBytes: 1024,
  maxPages: 10,
  guestRetentionHours: 24,
  uploadIntentTtlSeconds: 300,
} satisfies UploadPolicy;

describe("upload validation", () => {
  it("builds a typed upload intent for a supported document", () => {
    const file = new File(["fictional"], "fictional-resume.pdf", {
      type: "application/pdf",
    });
    expect(validateUpload(file, policy)).toEqual({
      input: {
        displayFilename: "fictional-resume.pdf",
        expectedSizeBytes: 9,
        mediaType: "application/pdf",
        purpose: "resume_health",
      },
    });
  });

  it("rejects oversize and mismatched browser metadata before upload", () => {
    expect(
      validateUpload(
        new File([new Uint8Array(1025)], "large.pdf", {
          type: "application/pdf",
        }),
        policy,
      ),
    ).toHaveProperty("error");
    expect(
      validateUpload(
        new File(["fictional"], "disguised.pdf", {
          type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }),
        policy,
      ),
    ).toEqual({
      error:
        "The filename and reported file type do not agree. Choose the original PDF or DOCX file.",
    });
  });
});
