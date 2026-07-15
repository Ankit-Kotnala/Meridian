"use client";

import type { components } from "@careeros/contracts";

import { fillApiPath } from "@/shared/api/api-path";
import {
  ApiRequestError,
  apiMutation,
  apiQuery,
} from "@/shared/api/browser-request";

import {
  parseCanonical,
  parseClaim,
  parseDocument,
  parseDocumentList,
  parseFinalizeUpload,
  parseJob,
  parseJobAccepted,
  parsePlainText,
  parseReadingOrder,
  parseReport,
  parseUploadIntent,
  parseUploadPolicy,
} from "./contract-parsers";
import type {
  CanonicalResume,
  CanonicalUpdate,
  ClaimGuestDocument,
  DocumentDetail,
  DocumentList,
  FinalizeUpload,
  JobAccepted,
  PlainText,
  ProcessingJob,
  ReadingOrder,
  ResumeHealthAccess,
  ResumeHealthReport,
  UploadIntent,
  UploadIntentInput,
  UploadPolicy,
} from "./types";

const account = {
  policy: "/api/v1/resume-health/upload-policy" as const,
  presign: "/api/v1/uploads/presign" as const,
};

const guest = {
  policy: "/api/v1/guest/resume-health/upload-policy" as const,
  presign: "/api/v1/guest/uploads/presign" as const,
};

function mutationCsrf(access: ResumeHealthAccess) {
  return access === "account" ? ("session" as const) : ("guest" as const);
}

function withIdempotency(idempotencyKey: string): HeadersInit {
  return { "Idempotency-Key": idempotencyKey };
}

export function newIdempotencyKey(): string {
  return crypto.randomUUID();
}

export async function getUploadPolicy(
  access: ResumeHealthAccess,
): Promise<UploadPolicy> {
  const response = await apiQuery(
    access === "account" ? account.policy : guest.policy,
    { retryAfterRefresh: access === "account" },
  );
  return parseUploadPolicy(await response.json());
}

export async function createUploadIntent(
  access: ResumeHealthAccess,
  input: UploadIntentInput,
): Promise<UploadIntent> {
  const response = await apiMutation(
    access === "account" ? account.presign : guest.presign,
    { method: "POST", body: JSON.stringify(input) },
    {
      csrf: access === "account" ? "session" : "pre-auth",
      retryAfterRefresh: access === "account",
    },
  );
  return parseUploadIntent(await response.json());
}

export async function finalizeUpload(
  access: ResumeHealthAccess,
  uploadId: string,
  idempotencyKey: string,
): Promise<FinalizeUpload> {
  const template =
    access === "account"
      ? "/api/v1/uploads/{upload_id}/finalize"
      : "/api/v1/guest/uploads/{upload_id}/finalize";
  const response = await apiMutation(
    fillApiPath(template, { upload_id: uploadId }),
    { method: "POST", headers: withIdempotency(idempotencyKey) },
    { csrf: mutationCsrf(access) },
  );
  return parseFinalizeUpload(await response.json());
}

export async function getDocuments(): Promise<DocumentList> {
  return parseDocumentList(
    await (
      await apiQuery("/api/v1/documents", { retryAfterRefresh: true })
    ).json(),
  );
}

export async function getDocument(
  access: ResumeHealthAccess,
  documentId: string,
): Promise<DocumentDetail> {
  const template =
    access === "account"
      ? "/api/v1/documents/{document_id}"
      : "/api/v1/guest/documents/{document_id}";
  return parseDocument(
    await (
      await apiQuery(fillApiPath(template, { document_id: documentId }), {
        retryAfterRefresh: access === "account",
      })
    ).json(),
  );
}

export async function getPlainText(
  access: ResumeHealthAccess,
  documentId: string,
): Promise<PlainText> {
  const template =
    access === "account"
      ? "/api/v1/documents/{document_id}/plain-text"
      : "/api/v1/guest/documents/{document_id}/plain-text";
  return parsePlainText(
    await (
      await apiQuery(fillApiPath(template, { document_id: documentId }), {
        retryAfterRefresh: access === "account",
      })
    ).json(),
  );
}

export async function getReadingOrder(
  access: ResumeHealthAccess,
  documentId: string,
): Promise<ReadingOrder> {
  const template =
    access === "account"
      ? "/api/v1/documents/{document_id}/reading-order"
      : "/api/v1/guest/documents/{document_id}/reading-order";
  return parseReadingOrder(
    await (
      await apiQuery(fillApiPath(template, { document_id: documentId }), {
        retryAfterRefresh: access === "account",
      })
    ).json(),
  );
}

export async function updateCanonicalResume(
  access: ResumeHealthAccess,
  documentId: string,
  version: number,
  input: CanonicalUpdate,
): Promise<CanonicalResume> {
  const template =
    access === "account"
      ? "/api/v1/documents/{document_id}/canonical-resume"
      : "/api/v1/guest/documents/{document_id}/canonical-resume";
  const response = await apiMutation(
    fillApiPath(template, { document_id: documentId }),
    {
      method: "PATCH",
      headers: { "If-Match": `"${version}"` },
      body: JSON.stringify(input),
    },
    { csrf: mutationCsrf(access) },
  );
  return parseCanonical(await response.json());
}

export async function startResumeHealth(
  access: ResumeHealthAccess,
  documentId: string,
  idempotencyKey: string,
): Promise<JobAccepted> {
  const path =
    access === "account"
      ? "/api/v1/resume-health"
      : "/api/v1/guest/resume-health";
  const body = {
    documentId,
  } satisfies components["schemas"]["ResumeHealthRequest"];
  const response = await apiMutation(
    path,
    {
      method: "POST",
      headers: withIdempotency(idempotencyKey),
      body: JSON.stringify(body),
    },
    { csrf: mutationCsrf(access) },
  );
  return parseJobAccepted(await response.json());
}

export async function getProcessingJob(
  access: ResumeHealthAccess,
  jobId: string,
  signal?: AbortSignal,
): Promise<ProcessingJob> {
  const template =
    access === "account"
      ? "/api/v1/processing-jobs/{job_id}"
      : "/api/v1/guest/processing-jobs/{job_id}";
  return parseJob(
    await (
      await apiQuery(fillApiPath(template, { job_id: jobId }), {
        retryAfterRefresh: access === "account",
        ...(signal ? { signal } : {}),
      })
    ).json(),
  );
}

export async function cancelProcessingJob(
  access: ResumeHealthAccess,
  jobId: string,
  idempotencyKey: string,
): Promise<ProcessingJob> {
  const template =
    access === "account"
      ? "/api/v1/processing-jobs/{job_id}/cancel"
      : "/api/v1/guest/processing-jobs/{job_id}/cancel";
  const response = await apiMutation(
    fillApiPath(template, { job_id: jobId }),
    { method: "POST", headers: withIdempotency(idempotencyKey) },
    { csrf: mutationCsrf(access) },
  );
  return parseJob(await response.json());
}

export async function getResumeHealthReport(
  access: ResumeHealthAccess,
  analysisId: string,
): Promise<ResumeHealthReport> {
  const template =
    access === "account"
      ? "/api/v1/resume-health/{analysis_id}"
      : "/api/v1/guest/resume-health/{analysis_id}";
  return parseReport(
    await (
      await apiQuery(fillApiPath(template, { analysis_id: analysisId }), {
        retryAfterRefresh: access === "account",
      })
    ).json(),
  );
}

export async function deleteDocument(
  access: ResumeHealthAccess,
  documentId: string,
  version: number,
): Promise<JobAccepted> {
  const template =
    access === "account"
      ? "/api/v1/documents/{document_id}"
      : "/api/v1/guest/documents/{document_id}";
  const response = await apiMutation(
    fillApiPath(template, { document_id: documentId }),
    {
      method: "DELETE",
      headers: {
        "If-Match": `"${version}"`,
        ...withIdempotency(newIdempotencyKey()),
      },
    },
    { csrf: mutationCsrf(access) },
  );
  return parseJobAccepted(await response.json());
}

export async function claimGuestDocument(
  documentId: string,
): Promise<ClaimGuestDocument> {
  const response = await apiMutation(
    fillApiPath("/api/v1/guest/documents/{document_id}/claim", {
      document_id: documentId,
    }),
    { method: "POST", body: JSON.stringify({ consent: true }) },
    { csrf: "session" },
  );
  return parseClaim(await response.json());
}

export class DirectUploadError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "DirectUploadError";
  }
}

function validatedUploadUrl(value: string): URL {
  const target = new URL(value);
  const configured = process.env.NEXT_PUBLIC_UPLOAD_ORIGIN;
  if (!configured) {
    throw new DirectUploadError("Secure upload is not configured.");
  }
  const allowed = new URL(configured);
  if (
    target.origin !== allowed.origin ||
    target.username ||
    target.password ||
    !new Set(["http:", "https:"]).has(target.protocol)
  ) {
    throw new DirectUploadError("The upload destination was not accepted.");
  }
  return target;
}

export function uploadFile(
  intent: UploadIntent,
  file: File,
  onProgress: (percent: number | null) => void,
  signal: AbortSignal,
): Promise<void> {
  const target = validatedUploadUrl(intent.url);
  if (signal.aborted) {
    return Promise.reject(
      new DirectUploadError("The file transfer was cancelled."),
    );
  }
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open(intent.method, target, true);
    request.withCredentials = false;
    for (const [name, value] of Object.entries(intent.headers)) {
      request.setRequestHeader(name, value);
    }
    request.upload.onprogress = (event) => {
      onProgress(
        event.lengthComputable && event.total > 0
          ? Math.min(100, (event.loaded / event.total) * 100)
          : null,
      );
    };
    request.onload = () => {
      if (request.status >= 200 && request.status < 300) resolve();
      else reject(new DirectUploadError("The file could not be transferred."));
    };
    request.onerror = () =>
      reject(new DirectUploadError("The file could not be transferred."));
    request.ontimeout = () =>
      reject(new DirectUploadError("The file transfer timed out."));
    request.onabort = () =>
      reject(new DirectUploadError("The file transfer was cancelled."));
    const abort = () => request.abort();
    signal.addEventListener("abort", abort, { once: true });
    request.onloadend = () => signal.removeEventListener("abort", abort);
    request.timeout = 120_000;
    request.send(file);
  });
}

export { ApiRequestError };
