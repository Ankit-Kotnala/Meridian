import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { createCareerOsClient } from "./index";

const openApiPath = fileURLToPath(
  new URL("../openapi/careeros.openapi.json", import.meta.url),
);
const openApi = JSON.parse(readFileSync(openApiPath, "utf8")) as {
  paths: Record<string, { get?: { operationId?: string } }>;
  components: { schemas: Record<string, unknown> };
};

describe("generated platform contracts", () => {
  it("contains every Phase 0 endpoint with a stable operation identifier", () => {
    expect(openApi.paths["/health"]?.get?.operationId).toBe("health");
    expect(openApi.paths["/ready"]?.get?.operationId).toBe("readiness");
    expect(openApi.paths["/api/v1/meta"]?.get?.operationId).toBe("metadata");
  });

  it("contains the four response models exported by this package", () => {
    expect(Object.keys(openApi.components.schemas)).toEqual(
      expect.arrayContaining([
        "ComponentReadiness",
        "HealthResponse",
        "MetaResponse",
        "ReadinessResponse",
      ]),
    );
  });

  it("creates a path-typed fetch client without making a request", () => {
    const client = createCareerOsClient("https://api.example.test");

    expect(client.GET).toBeTypeOf("function");
  });
});
