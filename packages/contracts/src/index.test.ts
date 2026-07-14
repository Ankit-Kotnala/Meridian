import { describe, expect, it } from "vitest";

import {
  apiErrorSchema,
  healthResponseSchema,
  readinessResponseSchema,
} from "./index";

describe("platform contracts", () => {
  it("accepts the API health envelope", () => {
    expect(
      healthResponseSchema.parse({
        status: "ok",
        service: "careeros-api",
        version: "0.1.0",
      }),
    ).toEqual({ status: "ok", service: "careeros-api", version: "0.1.0" });
  });

  it("rejects an unknown readiness state", () => {
    expect(() =>
      readinessResponseSchema.parse({
        status: "perfect",
        service: "careeros-api",
        version: "0.1.0",
        checks: {},
      }),
    ).toThrow();
  });

  it("accepts the documented problem response shape", () => {
    expect(
      apiErrorSchema.parse({
        type: "https://careeros.example/problems/validation-error",
        title: "Request validation failed",
        status: 422,
        code: "validation_error",
        detail: "Review the highlighted fields.",
        requestId: "01JEXAMPLE",
        errors: [
          {
            field: "startDate",
            code: "invalid_date",
            message: "Use an ISO date.",
          },
        ],
      }).code,
    ).toBe("validation_error");
  });
});
