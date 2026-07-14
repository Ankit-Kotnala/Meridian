import { afterEach, describe, expect, it, vi } from "vitest";

import { apiMutation, apiQuery } from "./browser-request";

function json(body: unknown, init?: ResponseInit) {
  return new Response(JSON.stringify(body), {
    headers: { "content-type": "application/json" },
    ...init,
  });
}

describe("browser API requests", () => {
  afterEach(() => {
    document.cookie = "careeros_csrf=; Max-Age=0; Path=/";
    vi.unstubAllGlobals();
  });

  it("uses the session-bound readable CSRF cookie for authenticated writes", async () => {
    document.cookie = "careeros_csrf=session-token; Path=/";
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await apiMutation(
      "/api/v1/me",
      { body: JSON.stringify({ displayName: "Alex" }), method: "PATCH" },
      { csrf: "session", retryAfterRefresh: false },
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(request.headers).get("x-csrf-token")).toBe(
      "session-token",
    );
  });

  it("coalesces concurrent refreshes and retries authenticated reads once", async () => {
    let resourceRequests = 0;
    const fetchMock = vi.fn(async (path: string) => {
      if (path === "/api/v1/me") {
        resourceRequests += 1;
        return resourceRequests <= 2
          ? json({ detail: "expired" }, { status: 401 })
          : json({ ok: true });
      }
      if (path === "/api/v1/auth/csrf") {
        return json({ csrfToken: "pre-auth-token" });
      }
      if (path === "/api/v1/auth/refresh") {
        return new Response(null, { status: 204 });
      }
      throw new Error(`Unexpected request: ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const [first, second] = await Promise.all([
      apiQuery("/api/v1/me", { retryAfterRefresh: true }),
      apiQuery("/api/v1/me", { retryAfterRefresh: true }),
    ]);

    expect(first.status).toBe(200);
    expect(second.status).toBe(200);
    expect(
      fetchMock.mock.calls.filter(([path]) => path === "/api/v1/auth/csrf"),
    ).toHaveLength(1);
    expect(
      fetchMock.mock.calls.filter(([path]) => path === "/api/v1/auth/refresh"),
    ).toHaveLength(1);
  });
});
