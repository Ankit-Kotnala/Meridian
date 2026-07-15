import {
  validateDisplayName,
  validateEmail,
  validatePassword,
} from "./auth-validation";
import { describe, expect, it } from "vitest";

describe("auth validation", () => {
  it("validates email without changing the submitted account state", () => {
    expect(validateEmail("person@example.com")).toBeUndefined();
    expect(validateEmail("not-an-email")).toBe("Enter a valid email address.");
  });

  it("applies bounded password guidance", () => {
    expect(validatePassword("long-enough-password")).toBeUndefined();
    expect(validatePassword("short")).toBe("Use at least 12 characters.");
    expect(validatePassword("x".repeat(129))).toBe(
      "Use no more than 128 characters.",
    );
  });

  it("requires a bounded display name", () => {
    expect(validateDisplayName("Alex Morgan")).toBeUndefined();
    expect(validateDisplayName(" ")).toBe(
      "Enter the name you want CareerOS to use.",
    );
  });
});
