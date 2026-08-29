import { describe, expect, it } from "vitest";

import { GET } from "@/app/api/health/route";

describe("GET /api/health", () => {
  it("reports the web process as healthy without caching", async () => {
    const response = GET();
    const body = (await response.json()) as {
      service: string;
      status: string;
      version: string;
    };

    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(body).toMatchObject({
      service: "rezumi-web",
      status: "ok",
      version: "0.1.0",
    });
  });
});
