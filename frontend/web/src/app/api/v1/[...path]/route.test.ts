import { afterEach, describe, expect, it, vi } from "vitest";

import { proxyApiRequest } from "@/shared/api/proxy-request";

const context = (path: string[]) => ({ params: Promise.resolve({ path }) });

describe("API proxy", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("forwards only approved request headers and preserves response cookies", async () => {
    vi.stubEnv("API_BASE_URL", "http://api:8000");
    const responseHeaders = new Headers({
      "content-type": "application/json",
      "x-internal-topology": "private",
    });
    responseHeaders.append(
      "set-cookie",
      "rezumi_session=one; HttpOnly; Path=/",
    );
    responseHeaders.append(
      "set-cookie",
      "rezumi_refresh=two; HttpOnly; Path=/",
    );

    const fetchMock = vi.fn().mockResolvedValue(
      new Response('{"ok":true}', {
        status: 201,
        headers: responseHeaders,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await proxyApiRequest(
      new Request("http://localhost:3000/api/v1/auth/login?next=dashboard", {
        method: "POST",
        headers: {
          authorization: "Bearer must-not-forward",
          cookie: "rezumi_csrf=token",
          origin: "http://localhost:3000",
          "if-match": '"4"',
          "x-csrf-token": "token",
          "x-forwarded-for": "203.0.113.8",
          "x-request-id": "request-1",
        },
        body: "{}",
      }),
      context(["auth", "login"]),
    );

    expect(response.status).toBe(201);
    expect(response.headers.getSetCookie()).toHaveLength(2);
    expect(response.headers.has("x-internal-topology")).toBe(false);

    const [destination, init] = fetchMock.mock.calls[0] as [URL, RequestInit];
    const headers = init.headers as Headers;
    expect(destination.toString()).toBe(
      "http://api:8000/api/v1/auth/login?next=dashboard",
    );
    expect(init.redirect).toBe("manual");
    expect(headers.get("cookie")).toBe("rezumi_csrf=token");
    expect(headers.get("x-csrf-token")).toBe("token");
    expect(headers.get("if-match")).toBe('"4"');
    expect(headers.has("authorization")).toBe(false);
    expect(headers.has("x-forwarded-for")).toBe(false);
  });

  it("returns a safe error when the upstream cannot be reached", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("connect ECONNREFUSED secret-host")),
    );

    const response = await proxyApiRequest(
      new Request("http://localhost:3000/api/v1/me"),
      context(["me"]),
    );
    const problem = (await response.json()) as {
      detail: string;
      status: number;
    };

    expect(response.status).toBe(503);
    expect(problem.status).toBe(503);
    expect(problem.detail).not.toContain("secret-host");
  });

  it("rejects an invalid path before contacting the upstream", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await proxyApiRequest(
      new Request("http://localhost:3000/api/v1/auth"),
      context([".."]),
    );

    expect(response.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
