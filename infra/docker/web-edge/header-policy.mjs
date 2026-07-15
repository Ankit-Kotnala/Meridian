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
