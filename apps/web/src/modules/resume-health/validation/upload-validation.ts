import type { UploadIntentInput, UploadPolicy } from "../api/types";

const PDF = "application/pdf" as const;
const DOCX =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document" as const;

export type ValidatedUpload = {
  input: UploadIntentInput;
};

export function validateUpload(
  file: File,
  policy: UploadPolicy,
): { error: string } | ValidatedUpload {
  if (file.size < 1) return { error: "Choose a file that is not empty." };
  if (file.size > policy.maxBytes) {
    return {
      error: `This file is larger than the ${Math.ceil(policy.maxBytes / 1_048_576)} MB upload limit.`,
    };
  }
  const extension = file.name.toLocaleLowerCase().split(".").pop();
  const extensionType =
    extension === "pdf" ? PDF : extension === "docx" ? DOCX : null;
  if (!extensionType) {
    return { error: "Choose a PDF or DOCX file." };
  }
  if (
    file.type &&
    !policy.acceptedMediaTypes.includes(
      file.type as (typeof policy.acceptedMediaTypes)[number],
    )
  ) {
    return {
      error:
        "The browser reported an unsupported file type. Choose a PDF or DOCX file.",
    };
  }
  if (
    file.type &&
    file.type !== extensionType &&
    policy.acceptedMediaTypes.includes(extensionType)
  ) {
    return {
      error:
        "The filename and reported file type do not agree. Choose the original PDF or DOCX file.",
    };
  }
  if (!policy.acceptedMediaTypes.includes(extensionType)) {
    return { error: "This document type is not currently accepted." };
  }
  return {
    input: {
      displayFilename: file.name,
      expectedSizeBytes: file.size,
      mediaType: extensionType,
      purpose: "resume_health",
    },
  };
}
