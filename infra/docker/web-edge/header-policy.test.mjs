import assert from "node:assert/strict";
import test from "node:test";

import {
  downstreamHeaders,
  exactUploadOrigin,
  upstreamHeaders,
} from "./header-policy.mjs";

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
test("public responses override unsafe upstream headers", () => {
  const result = downstreamHeaders({
    connection: "close",
    server: "framework-version",
    "x-powered-by": "framework",
    "content-security-policy": "default-src *",
    "set-cookie": ["session=opaque", "csrf=opaque"],
  });

  assert.equal(result.connection, undefined);
  assert.equal(result.server, undefined);
  assert.equal(result["x-powered-by"], undefined);
  assert.match(result["content-security-policy"], /frame-ancestors 'none'/u);
  assert.match(result["content-security-policy"], /script-src-attr 'none'/u);
  assert.equal(result["x-content-type-options"], "nosniff");
  assert.equal(result["x-frame-options"], "DENY");
  assert.deepEqual(result["set-cookie"], ["session=opaque", "csrf=opaque"]);
  assert.equal(result["strict-transport-security"], undefined);
});

test("public CSP admits only the validated direct-upload origin", () => {
  const result = downstreamHeaders({}, false, "https://uploads.example.test");

  assert.match(
    result["content-security-policy"],
    /connect-src 'self' https:\/\/uploads\.example\.test(?:;|$)/u,
  );
  assert.doesNotMatch(result["content-security-policy"], /connect-src[^;]*\*/u);
});

test("upload origins fail closed when they are not exact and trustworthy", () => {
  for (const value of [
    "*",
    "http://uploads.example.test",
    "https://user:secret@uploads.example.test",
    "https://uploads.example.test/path",
    "https://uploads.example.test?scope=wide",
  ]) {
    assert.throws(() => exactUploadOrigin(value), /EDGE_UPLOAD_ORIGIN/u);
  }
  assert.equal(
    exactUploadOrigin("http://127.0.0.1:19000"),
    "http://127.0.0.1:19000",
  );
});

test("TLS deployments opt into HSTS and insecure-request upgrading", () => {
  const result = downstreamHeaders({}, true);

  assert.equal(
    result["strict-transport-security"],
    "max-age=63072000; includeSubDomains; preload",
  );
  assert.match(result["content-security-policy"], /upgrade-insecure-requests/u);
});
