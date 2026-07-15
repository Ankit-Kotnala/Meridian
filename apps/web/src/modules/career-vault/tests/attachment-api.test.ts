import { afterEach, describe, expect, it, vi } from "vitest";

import {
  acceptProfileImportProposal,
  createAttachmentUploadIntent,
  uploadAttachment,
} from "../api/career-vault-api";
import type { EvidenceItem, ProfileImportProposal } from "../api/types";

const request = vi.hoisted(() => ({ mutation: vi.fn() }));

vi.mock("@/shared/api/browser-request", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/shared/api/browser-request")>()),
  apiMutation: request.mutation,
}));

class SuccessfulXmlHttpRequest {
  static instances: SuccessfulXmlHttpRequest[] = [];

  readonly headers = new Headers();
  readonly upload = {
    onprogress: null as ((event: ProgressEvent) => void) | null,
  };
  onabort: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onload: (() => void) | null = null;
  onloadend: (() => void) | null = null;
  ontimeout: (() => void) | null = null;
  status = 200;
  timeout = 0;
  url = "";
  withCredentials = true;

  constructor() {
    SuccessfulXmlHttpRequest.instances.push(this);
  }

  abort() {
    this.onabort?.();
    this.onloadend?.();
  }
  open(_method: string, url: URL) {
    this.url = String(url);
  }
  setRequestHeader(name: string, value: string) {
    this.headers.set(name, value);
  }
  send(body: File) {
    this.upload.onprogress?.({
      lengthComputable: true,
      loaded: body.size,
      total: body.size,
    } as ProgressEvent);
    this.onload?.();
    this.onloadend?.();
  }
}

const evidence = {
  id: "00000000-0000-4000-8000-000000000401",
  version: 3,
} as EvidenceItem;

describe("private evidence attachment API", () => {
  afterEach(() => {
    request.mutation.mockReset();
    SuccessfulXmlHttpRequest.instances = [];
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("binds the presign request to the exact filename, media type, and expected byte size", async () => {
    request.mutation.mockResolvedValue(
      new Response(
        JSON.stringify({
          attachmentId: "00000000-0000-4000-8000-000000000402",
          expiresAt: "2026-07-15T00:05:00Z",
          headers: { "content-type": "application/pdf" },
          method: "PUT",
          uploadId: "00000000-0000-4000-8000-000000000403",
          url: "http://localhost:9000/private/signed-object",
        }),
        { status: 200 },
      ),
    );
    const file = new File(["fictional"], "support.pdf", {
      type: "application/pdf",
    });

    await createAttachmentUploadIntent(evidence, file);

    const init = request.mutation.mock.calls[0]?.[1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({
      displayFilename: "support.pdf",
      expectedSizeBytes: file.size,
      mediaType: "application/pdf",
    });
    expect(new Headers(init.headers).get("If-Match")).toBe('"3"');
  });

  it("maps reviewed proposal change IDs back to allow-listed field names", async () => {
    request.mutation.mockRejectedValue(new Error("stop after request capture"));
    const proposal = {
      changes: [
        {
          field: "title",
          id: "00000000-0000-4000-8000-000000000404",
          proposedValue: "Proposed title",
        },
      ],
      id: "00000000-0000-4000-8000-000000000405",
      version: 2,
    } as ProfileImportProposal;

    await expect(
      acceptProfileImportProposal(proposal, {
        [proposal.changes[0]!.id]: "Reviewed title",
      }),
    ).rejects.toThrow("stop after request capture");

    const init = request.mutation.mock.calls[0]?.[1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({
      edits: { title: "Reviewed title" },
    });
  });

  it("uploads only to the configured origin without cookies and reports progress", async () => {
    vi.stubEnv("NEXT_PUBLIC_UPLOAD_ORIGIN", "http://localhost:9000");
    vi.stubGlobal("XMLHttpRequest", SuccessfulXmlHttpRequest);
    const progress = vi.fn();
    const file = new File(["fictional"], "support.pdf", {
      type: "application/pdf",
    });

    await uploadAttachment(
      {
        attachmentId: "00000000-0000-4000-8000-000000000402",
        expiresAt: "2026-07-15T00:05:00Z",
        headers: { "content-type": "application/pdf" },
        method: "PUT",
        uploadId: "00000000-0000-4000-8000-000000000403",
        url: "http://localhost:9000/private/signed-object",
      },
      file,
      progress,
      new AbortController().signal,
    );

    const transfer = SuccessfulXmlHttpRequest.instances[0];
    expect(transfer?.url).toBe("http://localhost:9000/private/signed-object");
    expect(transfer?.withCredentials).toBe(false);
    expect(progress).toHaveBeenLastCalledWith(100);
  });

  it("rejects a cross-origin or already-cancelled upload", async () => {
    vi.stubEnv("NEXT_PUBLIC_UPLOAD_ORIGIN", "https://uploads.example.test");
    const intent = {
      attachmentId: "00000000-0000-4000-8000-000000000402",
      expiresAt: "2026-07-15T00:05:00Z",
      headers: {},
      method: "PUT" as const,
      uploadId: "00000000-0000-4000-8000-000000000403",
      url: "https://other.example.test/private/object",
    };
    expect(() =>
      uploadAttachment(
        intent,
        new File(["x"], "x.pdf"),
        vi.fn(),
        new AbortController().signal,
      ),
    ).toThrow("destination was not accepted");

    intent.url = "https://uploads.example.test/private/object";
    const controller = new AbortController();
    controller.abort();
    await expect(
      uploadAttachment(
        intent,
        new File(["x"], "x.pdf"),
        vi.fn(),
        controller.signal,
      ),
    ).rejects.toThrow("cancelled");
  });
});
