import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createAccountExportDownload,
  getAccountOperation,
  requestAccountDeletion,
  requestAccountExport,
} from "../api/settings-api";

const operationToken = "t".repeat(80);
const operation = {
  artifactExpiresAt: null,
  artifactSha256: null,
  artifactSizeBytes: null,
  attempts: 0,
  blockedReason: null,
  completedAt: null,
  id: "00000000-0000-4000-8000-000000000911",
  kind: "export",
  maxAttempts: 5,
  operationToken,
  requestedAt: "2026-07-27T04:00:00Z",
  status: "queued",
  updatedAt: "2026-07-27T04:00:00Z",
};

function json(body: unknown) {
  return new Response(JSON.stringify(body), {
    headers: { "content-type": "application/json" },
    status: 200,
  });
}

describe("privacy settings API", () => {
  beforeEach(() => {
    document.cookie = "careeros_csrf=session-csrf; Path=/";
  });

  afterEach(() => {
    document.cookie = "careeros_csrf=; Max-Age=0; Path=/";
    vi.unstubAllGlobals();
  });

  it("sends CSRF and a caller-stable idempotency key for export and deletion", async () => {
    const fetchMock = vi.fn<
      (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    >(async () => json(operation));
    vi.stubGlobal("fetch", fetchMock);

    await requestAccountExport("settings-export:stable-key");
    await requestAccountDeletion("settings-deletion:stable-key");

    const exportHeaders = new Headers(fetchMock.mock.calls[0]?.[1]?.headers);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/account-exports");
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe("POST");
    expect(exportHeaders.get("Idempotency-Key")).toBe(
      "settings-export:stable-key",
    );
    expect(exportHeaders.get("X-CSRF-Token")).toBe("session-csrf");

    const deletionHeaders = new Headers(fetchMock.mock.calls[1]?.[1]?.headers);
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/v1/account-deletions");
    expect(deletionHeaders.get("Idempotency-Key")).toBe(
      "settings-deletion:stable-key",
    );
    expect(deletionHeaders.get("X-CSRF-Token")).toBe("session-csrf");
  });

  it("uses the operation capability for status and short-lived download reads", async () => {
    const fetchMock = vi
      .fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(
        async () => json({}),
      )
      .mockResolvedValueOnce(json({ ...operation, operationToken: undefined }))
      .mockResolvedValueOnce(
        json({
          downloadUrl: "https://downloads.invalid/account-export.zip",
          expiresInSeconds: 120,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await getAccountOperation(operation.id, operationToken);
    await createAccountExportDownload(operation.id, operationToken);

    for (const call of fetchMock.mock.calls) {
      expect(
        new Headers(call[1]?.headers).get("X-Account-Operation-Token"),
      ).toBe(operationToken);
      expect(call[1]?.credentials).toBe("same-origin");
      expect(call[1]?.cache).toBe("no-store");
    }
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      `/api/v1/account-operations/${operation.id}`,
    );
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      `/api/v1/account-operations/${operation.id}/download`,
    );
  });

  it("fails closed on a malformed capability response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json({ ...operation, operationToken: "short" })),
    );

    await expect(
      requestAccountExport("settings-export:invalid"),
    ).rejects.toThrow("Invalid account operation capability");
  });
});
