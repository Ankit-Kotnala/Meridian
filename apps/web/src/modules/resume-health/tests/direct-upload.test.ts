import { afterEach, describe, expect, it, vi } from "vitest";

import { uploadFile } from "../api/resume-health-api";
import type { UploadIntent } from "../api/types";

const intent = {
  uploadId: "00000000-0000-4000-8000-000000000001",
  url: "http://localhost:9000/careeros-documents/signed-object?signature=test",
  method: "PUT",
  headers: { "content-type": "application/pdf" },
  expiresAt: "2026-07-15T00:05:00Z",
  guestExpiresAt: null,
} satisfies UploadIntent;

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

  send(body: File) {
    this.upload.onprogress?.({
      lengthComputable: true,
      loaded: body.size,
      total: body.size,
    } as ProgressEvent);
    this.onload?.();
    this.onloadend?.();
  }

  setRequestHeader(name: string, value: string) {
    this.headers.set(name, value);
  }
}

describe("direct resume upload", () => {
  afterEach(() => {
    SuccessfulXmlHttpRequest.instances = [];
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("uploads only to the configured origin and reports real byte progress", async () => {
    vi.stubEnv("NEXT_PUBLIC_UPLOAD_ORIGIN", "http://localhost:9000");
    vi.stubGlobal("XMLHttpRequest", SuccessfulXmlHttpRequest);
    const progress = vi.fn();
    const file = new File(["fictional"], "fictional.pdf", {
      type: "application/pdf",
    });

    await expect(
      uploadFile(intent, file, progress, new AbortController().signal),
    ).resolves.toBeUndefined();

    const request = SuccessfulXmlHttpRequest.instances[0];
    expect(request?.url).toBe(intent.url);
    expect(request?.withCredentials).toBe(false);
    expect(request?.headers.get("content-type")).toBe("application/pdf");
    expect(progress).toHaveBeenLastCalledWith(100);
  });

  it("rejects a presigned destination on a different origin", () => {
    vi.stubEnv("NEXT_PUBLIC_UPLOAD_ORIGIN", "https://uploads.example.test");

    expect(() =>
      uploadFile(
        intent,
        new File(["fictional"], "fictional.pdf"),
        vi.fn(),
        new AbortController().signal,
      ),
    ).toThrow("The upload destination was not accepted.");
  });

  it("does not start a transfer after navigation has already aborted it", async () => {
    vi.stubEnv("NEXT_PUBLIC_UPLOAD_ORIGIN", "http://localhost:9000");
    vi.stubGlobal("XMLHttpRequest", SuccessfulXmlHttpRequest);
    const controller = new AbortController();
    controller.abort();

    await expect(
      uploadFile(
        intent,
        new File(["fictional"], "fictional.pdf"),
        vi.fn(),
        controller.signal,
      ),
    ).rejects.toThrow("The file transfer was cancelled.");
    expect(SuccessfulXmlHttpRequest.instances).toHaveLength(0);
  });
});
