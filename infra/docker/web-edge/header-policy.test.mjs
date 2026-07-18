import assert from "node:assert/strict";
import test from "node:test";

import { upstreamHeaders } from "./header-policy.mjs";

test("trusted edge overwrites every client-selected address header", () => {
  const result = upstreamHeaders(
    {
      connection: "keep-alive",
      cookie: "session=opaque",
      forwarded: "for=198.51.100.9",
      "x-forwarded-for": "203.0.113.77",
      "x-real-ip": "203.0.113.88",
    },
    "192.0.2.41",
  );

  assert.equal(result["x-forwarded-for"], "192.0.2.41");
  assert.equal(result["x-real-ip"], "192.0.2.41");
  assert.equal(result.forwarded, undefined);
  assert.equal(result.connection, undefined);
  assert.equal(result.cookie, "session=opaque");
});

test("trusted edge never forwards malformed socket metadata", () => {
  const result = upstreamHeaders({}, "spoofed\r\nx-forwarded-for: 1.2.3.4");

  assert.equal(result["x-forwarded-for"], "unavailable");
  assert.equal(result["x-real-ip"], "unavailable");
});
