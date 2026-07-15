import { describe, expect, it } from "vitest";

import { fillApiPath } from "./api-path";

describe("fillApiPath", () => {
  it("encodes generated path parameters as single path segments", () => {
    expect(
      fillApiPath("/api/v1/auth/sessions/{session_id}", {
        session_id: "device/../secondary",
      }),
    ).toBe("/api/v1/auth/sessions/device%2F..%2Fsecondary");
  });

  it("fails instead of emitting an unresolved generated path", () => {
    expect(() =>
      fillApiPath("/api/v1/auth/sessions/{session_id}", {
        session_id: undefined as unknown as string,
      }),
    ).toThrow();
  });
});
