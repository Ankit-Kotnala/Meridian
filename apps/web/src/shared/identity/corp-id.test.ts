import { describe, expect, it } from "vitest";

import { corpIdFor, corpIdStanding } from "./corp-id";

describe("corpIdFor", () => {
  it("derives a stable formatted identifier from an account UUID", () => {
    const id = corpIdFor("00000000-0000-4000-8000-0000000003e7");

    expect(id).toMatch(/^RZ-[0-9A-Z]{5}-[0-9A-Z]{5}$/);
    expect(corpIdFor("00000000-0000-4000-8000-0000000003e7")).toBe(id);
  });

  it("accepts an unhyphenated UUID and is case insensitive", () => {
    expect(corpIdFor("0000000000004000800000000000ABCD")).toBe(
      corpIdFor("00000000-0000-4000-8000-00000000abcd"),
    );
  });

  it("separates accounts that differ only in their low bits", () => {
    expect(corpIdFor("00000000-0000-4000-8000-000000000001")).not.toBe(
      corpIdFor("00000000-0000-4000-8000-000000000002"),
    );
  });

  it("never emits ambiguous characters", () => {
    for (const suffix of ["0001", "abcd", "ffff", "1234", "9999"]) {
      const id = corpIdFor(`00000000-0000-4000-8000-00000000${suffix}`);
      expect(id).not.toBeNull();
      expect(id?.slice(3)).not.toMatch(/[ILOU]/);
    }
  });

  it("returns null instead of inventing an identifier", () => {
    expect(corpIdFor("not-a-uuid")).toBeNull();
    expect(corpIdFor("")).toBeNull();
    expect(corpIdFor("00000000-0000-4000-8000-00000000000")).toBeNull();
  });
});

describe("corpIdStanding", () => {
  it("withholds standing until the email is confirmed", () => {
    const standing = corpIdStanding({
      confirmedEvidence: 5,
      emailVerified: false,
      experiences: 4,
    });

    expect(standing.tier).toBe("unverified");
    expect(standing.next).toBe("Confirm your email address.");
  });

  it("recognizes a confirmed email as the first tier", () => {
    const standing = corpIdStanding({
      confirmedEvidence: 0,
      emailVerified: true,
      experiences: 0,
    });

    expect(standing.tier).toBe("registered");
    expect(standing.attests).toContain("control of this email address");
  });

  it("raises standing once a career record exists", () => {
    expect(
      corpIdStanding({
        confirmedEvidence: 0,
        emailVerified: true,
        experiences: 2,
      }).tier,
    ).toBe("profiled");
  });

  it("reaches the top tier only with user-confirmed evidence", () => {
    const standing = corpIdStanding({
      confirmedEvidence: 1,
      emailVerified: true,
      experiences: 2,
    });

    expect(standing.tier).toBe("evidenced");
    expect(standing.next).toBeUndefined();
  });

  it("never claims an employer or third-party judgement", () => {
    for (const checks of [
      { confirmedEvidence: 0, emailVerified: false, experiences: 0 },
      { confirmedEvidence: 0, emailVerified: true, experiences: 0 },
      { confirmedEvidence: 0, emailVerified: true, experiences: 3 },
      { confirmedEvidence: 9, emailVerified: true, experiences: 3 },
    ]) {
      expect(corpIdStanding(checks).attests).not.toMatch(
        /employer|hiring|background|applicant.tracking/i,
      );
    }
  });
});
