const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

const CLIENT_ADDRESS_HEADERS = new Set([
  "cf-connecting-ip",
  "forwarded",
  "true-client-ip",
  "x-forwarded-for",
  "x-real-ip",
]);

export function upstreamHeaders(incoming, remoteAddress) {
  const headers = {};
  for (const [rawName, value] of Object.entries(incoming)) {
    const name = rawName.toLowerCase();
    if (
      value === undefined ||
      HOP_BY_HOP_HEADERS.has(name) ||
      CLIENT_ADDRESS_HEADERS.has(name)
    ) {
      continue;
    }
    headers[name] = value;
  }

  const peer = validRemoteAddress(remoteAddress)
    ? remoteAddress
    : "unavailable";
  headers["x-forwarded-for"] = peer;
  headers["x-real-ip"] = peer;
  headers["x-forwarded-proto"] = "http";
  return headers;
}

function validRemoteAddress(value) {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= 128 &&
    !/[\u0000-\u0020\u007f]/u.test(value)
  );
}
const CONTROLLED_RESPONSE_HEADERS = new Set([
  "content-security-policy",
  "cross-origin-opener-policy",
  "cross-origin-resource-policy",
  "permissions-policy",
  "referrer-policy",
  "server",
  "strict-transport-security",
  "x-content-type-options",
  "x-frame-options",
  "x-permitted-cross-domain-policies",
  "x-powered-by",
]);

export function exactUploadOrigin(configured) {
  let value;
  try {
    value = new URL(configured);
  } catch {
    throw new Error("EDGE_UPLOAD_ORIGIN must be an exact URL origin.");
  }
  const normalized = configured.replace(/\/$/u, "");
  const localHttp =
    value.protocol === "http:" &&
    new Set(["localhost", "127.0.0.1", "[::1]"]).has(value.hostname);
  if (
    value.origin !== normalized ||
    (value.protocol !== "https:" && !localHttp) ||
    value.username ||
    value.password
  ) {
    throw new Error(
      "EDGE_UPLOAD_ORIGIN must be one exact HTTPS origin or a local HTTP origin.",
    );
  }
  return value.origin;
}

export function downstreamHeaders(
  incoming,
  enableHsts = false,
  uploadOrigin = "http://localhost:9000",
) {
  const headers = {};
  for (const [rawName, value] of Object.entries(incoming)) {
    const name = rawName.toLowerCase();
    if (
      value === undefined ||
      HOP_BY_HOP_HEADERS.has(name) ||
      CONTROLLED_RESPONSE_HEADERS.has(name)
    ) {
      continue;
    }
    headers[name] = value;
  }

  const policy = [
    "default-src 'self'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "object-src 'none'",
    "script-src 'self' 'unsafe-inline'",
    "script-src-attr 'none'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    `connect-src 'self' ${exactUploadOrigin(uploadOrigin)}`,
    "worker-src 'self' blob:",
    "manifest-src 'self'",
    "media-src 'self'",
  ];
  if (enableHsts) policy.push("upgrade-insecure-requests");

  headers["content-security-policy"] = policy.join("; ");
  headers["cross-origin-opener-policy"] = "same-origin";
  headers["cross-origin-resource-policy"] = "same-origin";
  headers["permissions-policy"] =
    "camera=(), microphone=(), geolocation=(), payment=(), usb=()";
  headers["referrer-policy"] = "strict-origin-when-cross-origin";
  headers["x-content-type-options"] = "nosniff";
  headers["x-frame-options"] = "DENY";
  headers["x-permitted-cross-domain-policies"] = "none";
  if (enableHsts) {
    headers["strict-transport-security"] =
      "max-age=63072000; includeSubDomains; preload";
  }
  return headers;
}
