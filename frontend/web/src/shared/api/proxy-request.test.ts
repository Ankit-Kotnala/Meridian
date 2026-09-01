import { afterEach, describe, expect, it, vi } from "vitest";

import { proxyApiRequest } from "./proxy-request";

describe("API proxy request forwarding", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("forwards guest mutation controls and strips arbitrary headers", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        Response.json(
          { ok: true },
          { headers: { "x-request-id": "request-1" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    const response = await proxyApiRequest(
      new Request(
        "http://localhost/api/v1/guest/resume-health/uploads/policy",
        {
          headers: {
            "x-forwarded-for": "203.0.113.42",
            "x-guest-csrf": "guest-token",
            "x-private-client-data": "must-not-leave-the-web-tier",
          },
        },
      ),
      {
        params: Promise.resolve({
          path: ["guest", "resume-health", "uploads", "policy"],
        }),
      },
    );

    expect(response.status).toBe(200);
    const [destination, init] = fetchMock.mock.calls[0] as [URL, RequestInit];
    expect(destination.href).toBe(
      "http://127.0.0.1:8000/api/v1/guest/resume-health/uploads/policy",
    );
    const headers = new Headers(init.headers);
    expect(headers.get("x-guest-csrf")).toBe("guest-token");
    expect(headers.has("x-private-client-data")).toBe(false);
    expect(headers.get("x-rezumi-client-signal")).toMatch(
      /^v1\.[A-Za-z0-9_-]+\.[0-9a-f]{64}$/,
    );
  });

  it("canonicalizes equivalent IPv6 edge values into one abuse-control key", async () => {
    const signals: string[] = [];
    const fetchMock = vi.fn().mockImplementation((_url, init: RequestInit) => {
      signals.push(
        new Headers(init.headers).get("x-rezumi-client-signal") ?? "",
      );
      return Promise.resolve(Response.json({ ok: true }));
    });
    vi.stubGlobal("fetch", fetchMock);
    const context = {
      params: Promise.resolve({ path: ["auth", "register"] }),
    };

    await proxyApiRequest(
      new Request("http://localhost/api/v1/auth/register", {
        headers: {
          "x-forwarded-for": "2001:0db8:0000:0000:0000:0000:0000:0001",
        },
      }),
      context,
    );
    await proxyApiRequest(
      new Request("http://localhost/api/v1/auth/register", {
        headers: { "x-forwarded-for": "2001:db8::1" },
      }),
      context,
    );

    expect(signals).toHaveLength(2);
    expect(signals[0]).toBe(signals[1]);
  });

  it("fails closed when the production BFF signing key is absent", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubEnv("REZUMI_ENVIRONMENT", "production");
    vi.stubEnv("API_BFF_CLIENT_SIGNAL_SECRET", "");

    const response = await proxyApiRequest(
      new Request("http://localhost/api/v1/auth/register", {
        headers: { "x-forwarded-for": "203.0.113.42" },
      }),
      { params: Promise.resolve({ path: ["auth", "register"] }) },
    );

    expect(response.status).toBe(503);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("forwards a decoded slash inside one catalog-id segment", async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    const listingId =
      "https://himalayas.app/companies/acme/jobs/backend-engineer";

    const response = await proxyApiRequest(
      new Request(
        "http://localhost/api/v1/job-catalog/himalayas/listing/save",
        {
          method: "POST",
        },
      ),
      {
        params: Promise.resolve({
          path: ["job-catalog", "himalayas", listingId, "save"],
        }),
      },
    );

    expect(response.status).toBe(200);
    const [destination] = fetchMock.mock.calls[0] as [URL, RequestInit];
    expect(destination.pathname).toBe(
      `/api/v1/job-catalog/himalayas/${encodeURIComponent(listingId)}/save`,
    );
  });
});
