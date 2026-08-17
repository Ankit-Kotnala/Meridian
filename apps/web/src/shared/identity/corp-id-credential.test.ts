import { describe, expect, it } from "vitest";

import {
  CREDENTIAL_HEIGHT,
  CREDENTIAL_WIDTH,
  credentialFileName,
  credentialSvg,
} from "./corp-id-credential";

const base = {
  checks: { confirmedEvidence: 2, emailVerified: true, experiences: 3 },
  corpId: "RZ-4K7QP-2WX9M",
  displayName: "Ankit Kotnala",
  generatedOn: "2026-08-18",
};

describe("credentialSvg", () => {
  it("produces a self-contained SVG at the credential size", () => {
    const svg = credentialSvg(base);

    expect(svg.startsWith("<svg")).toBe(true);
    expect(svg).toContain(`width="${CREDENTIAL_WIDTH}"`);
    expect(svg).toContain(`height="${CREDENTIAL_HEIGHT}"`);
    expect(svg).toContain('xmlns="http://www.w3.org/2000/svg"');
    // No theme tokens: the artifact must rasterize identically for everyone.
    expect(svg).not.toContain("var(--");
  });

  it("carries the holder, identifier, standing, and generation date", () => {
    const svg = credentialSvg(base);

    expect(svg).toContain("ANKIT KOTNALA");
    expect(svg).toContain("RZ-4K7QP-2WX9M");
    expect(svg).toContain("EVIDENCED");
    expect(svg).toContain("2026-08-18");
  });

  it("always states the credential's limits", () => {
    const svg = credentialSvg(base);

    expect(svg).toContain(
      "Not an employer credential, a background check, a third-party identity verification, or a hiring signal.",
    );
  });

  it("downgrades the printed standing when checks are not met", () => {
    const svg = credentialSvg({
      ...base,
      checks: { confirmedEvidence: 0, emailVerified: false, experiences: 0 },
    });

    expect(svg).toContain("UNVERIFIED");
    expect(svg).not.toContain("EVIDENCED");
  });

  it("escapes holder names so markup cannot be injected", () => {
    const svg = credentialSvg({
      ...base,
      displayName: '<script>alert("x")</script>',
    });

    expect(svg).not.toContain("<script>");
    expect(svg).toContain("&lt;SCRIPT&gt;");
  });

  it("truncates an overlong name instead of overflowing the artwork", () => {
    const svg = credentialSvg({ ...base, displayName: "A".repeat(90) });

    expect(svg).toContain("…");
    expect(svg).not.toContain("A".repeat(40));
  });

  it("varies the decorative bars with the identifier", () => {
    expect(credentialSvg(base)).not.toBe(
      credentialSvg({ ...base, corpId: "RZ-00000-00001" }),
    );
  });
});

describe("credentialFileName", () => {
  it("names the download after the identifier", () => {
    expect(credentialFileName("RZ-4K7QP-2WX9M", "png")).toBe(
      "rezumi-corp-id-rz-4k7qp-2wx9m.png",
    );
    expect(credentialFileName("RZ-4K7QP-2WX9M", "svg")).toBe(
      "rezumi-corp-id-rz-4k7qp-2wx9m.svg",
    );
  });
});
