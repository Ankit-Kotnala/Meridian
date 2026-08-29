import { describe, expect, it } from "vitest";

import { buildApiQueryString } from "./api-query-string";

describe("generated API query strings", () => {
  it("encodes bounded scalar and repeated array parameters", () => {
    expect(
      buildApiQueryString({
        after: "cursor+/= value",
        includeArchived: false,
        limit: 25,
        omitted: undefined,
        state: ["confirmed", "supported"],
      }),
    ).toBe(
      "?after=cursor%2B%2F%3D+value&includeArchived=false&limit=25&state=confirmed&state=supported",
    );
  });

  it("omits nullish and empty-array parameters", () => {
    expect(buildApiQueryString({ after: null, state: [] })).toBe("");
  });

  it.each([
    [{ "unsafe&key": "value" }, TypeError],
    [{ limit: Number.NaN }, RangeError],
    [{ search: "unsafe\nvalue" }, RangeError],
    [{ search: "x".repeat(2_049) }, RangeError],
    [{ state: Array.from({ length: 101 }, () => "confirmed") }, RangeError],
    [
      Object.fromEntries(
        Array.from({ length: 101 }, (_, index) => [`filter${index}`, null]),
      ),
      RangeError,
    ],
  ])("rejects unsafe or unbounded parameters", (parameters, error) => {
    expect(() => buildApiQueryString(parameters)).toThrow(error);
  });

  it("rejects runtime object values even if an untyped caller bypasses TypeScript", () => {
    expect(() =>
      buildApiQueryString({ filter: { state: "confirmed" } } as never),
    ).toThrow(TypeError);
  });
});
