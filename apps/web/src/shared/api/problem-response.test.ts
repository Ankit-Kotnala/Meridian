import { describe, expect, it } from "vitest";

import { apiFailure } from "./problem-response";

function problem(body: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers);
  headers.set("content-type", "application/problem+json");
  return new Response(JSON.stringify(body), {
    ...init,
    headers,
  });
}

describe("API problem responses", () => {
  it("preserves bounded machine-readable problem and retry metadata", async () => {
    const failure = await apiFailure(
      problem(
        {
          code: "validation_error",
          detail: "Review the highlighted fields.",
          errors: [
            {
              code: "invalid_date",
              field: "startDate",
              message: "Use an ISO 8601 calendar date.",
            },
          ],
          requestId: "request-123",
          status: 200,
        },
        { headers: { "retry-after": "30" }, status: 422 },
      ),
    );

    expect(failure).toEqual({
      code: "validation_error",
      errors: [
        {
          code: "invalid_date",
          field: "startDate",
          message: "Use an ISO 8601 calendar date.",
        },
      ],
      message: "Review the highlighted fields.",
      requestId: "request-123",
      retryAfterSeconds: 30,
      status: 422,
    });
  });

  it("caps field errors and drops malformed or unsafe metadata", async () => {
    const errors = Array.from({ length: 25 }, (_, index) => ({
      code: "invalid_value",
      field: `items.${index}`,
      message: "Review this field.",
    }));
    errors[0] = {
      code: "INVALID VALUE",
      field: "unsafe\nfield",
      message: "unsafe\u202etext",
    };

    const failure = await apiFailure(
      problem(
        {
          code: "not valid",
          detail: "x".repeat(1_001),
          errors,
          requestId: "unsafe request id",
        },
        {
          headers: {
            "retry-after": "999999",
            "x-request-id": "safe-header-request-id",
          },
          status: 400,
        },
      ),
    );

    expect(failure.code).toBeUndefined();
    expect(failure.errors).toHaveLength(19);
    expect(failure.message).toBe("Something went wrong. Please try again.");
    expect(failure.requestId).toBe("safe-header-request-id");
    expect(failure.retryAfterSeconds).toBeUndefined();
    expect(failure.status).toBe(400);
  });

  it("falls back safely for a non-JSON response", async () => {
    const response = new Response("upstream details", {
      headers: { "content-type": "text/plain" },
      status: 502,
    });

    await expect(apiFailure(response)).resolves.toEqual({
      message: "Something went wrong. Please try again.",
      status: 502,
    });
  });
});
