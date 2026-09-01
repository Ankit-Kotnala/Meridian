import { createHmac } from "node:crypto";
import { isIP } from "node:net";

const REQUEST_HEADERS = new Set([
  "accept",
  "accept-language",
  "content-type",
  "cookie",
  "idempotency-key",
  "if-match",
  "origin",
  "traceparent",
  "tracestate",
  "user-agent",
  "x-csrf-token",
  "x-guest-csrf",
  "x-request-id",
]);

const RESPONSE_HEADERS = new Set([
  "cache-control",
  "content-disposition",
  "content-language",
  "content-type",
  "etag",
  "location",
  "retry-after",
  "traceparent",
  "vary",
  "x-request-id",
]);

const DEFAULT_TIMEOUT_MS = 10_000;
const MIN_TIMEOUT_MS = 1_000;
const MAX_TIMEOUT_MS = 30_000;
const BFF_SIGNAL_CONTEXT = "rezumi-bff-client-v1\0";
const DEVELOPMENT_BFF_SIGNAL_SECRET =
  "change-me-local-only-bff-client-signal-secret";
const TRUSTED_CLIENT_IP_HEADERS = new Set([
  "cf-connecting-ip",
  "true-client-ip",
  "x-forwarded-for",
  "x-real-ip",
]);

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

type StreamingRequestInit = RequestInit & { duplex?: "half" };

function apiOrigin(): URL {
  const configured = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
  const value = new URL(configured);

  if (!new Set(["http:", "https:"]).has(value.protocol)) {
    throw new Error("API_BASE_URL must use HTTP or HTTPS.");
  }
  if (value.username || value.password || value.search || value.hash) {
    throw new Error(
      "API_BASE_URL must not contain credentials or URL metadata.",
    );
  }
  if (value.pathname !== "/") {
    throw new Error("API_BASE_URL must be an origin without a path.");
  }
  return value;
}

function timeoutMilliseconds(): number {
  const parsed = Number(process.env.API_PROXY_TIMEOUT_MS ?? DEFAULT_TIMEOUT_MS);
  if (
    !Number.isInteger(parsed) ||
    parsed < MIN_TIMEOUT_MS ||
    parsed > MAX_TIMEOUT_MS
  ) {
    return DEFAULT_TIMEOUT_MS;
  }
  return parsed;
}

function forwardedRequestHeaders(source: Headers): Headers {
  const headers = new Headers();
  for (const [name, value] of source.entries()) {
    if (REQUEST_HEADERS.has(name.toLowerCase())) headers.append(name, value);
  }
  return headers;
}

function signedClientSignal(source: Headers): string {
  const trustedHeader =
    process.env.API_TRUSTED_CLIENT_IP_HEADER ?? "x-forwarded-for";
  if (!TRUSTED_CLIENT_IP_HEADERS.has(trustedHeader.toLowerCase())) {
    throw new Error(
      "API_TRUSTED_CLIENT_IP_HEADER is not an allowed edge header.",
    );
  }
  const raw = source.get(trustedHeader)?.split(",", 1)[0]?.trim();
  const address = normalizeClientAddress(raw);
  const configuredSecret = process.env.API_BFF_CLIENT_SIGNAL_SECRET;
  const secret = configuredSecret ?? DEVELOPMENT_BFF_SIGNAL_SECRET;
  if (
    Buffer.byteLength(secret, "utf8") < 32 ||
    (new Set(["production", "staging"]).has(
      process.env.REZUMI_ENVIRONMENT ?? "development",
    ) &&
      (!configuredSecret || configuredSecret === DEVELOPMENT_BFF_SIGNAL_SECRET))
  ) {
    throw new Error(
      "API_BFF_CLIENT_SIGNAL_SECRET must be a non-development value of at least 32 bytes.",
    );
  }
  const encoded = Buffer.from(address, "ascii").toString("base64url");
  const signature = createHmac("sha256", secret)
    .update(BFF_SIGNAL_CONTEXT)
    .update(address, "ascii")
    .digest("hex");
  return `v1.${encoded}.${signature}`;
}

function normalizeClientAddress(value: string | undefined): string {
  const version = value ? isIP(value) : 0;
  if (version === 4) return value as string;
  if (version === 6) {
    const hostname = new URL(`http://[${value}]/`).hostname;
    return hostname.slice(1, -1);
  }
  return "unavailable";
}

function forwardedResponseHeaders(source: Headers): Headers {
  const headers = new Headers();
  for (const [name, value] of source.entries()) {
    const normalized = name.toLowerCase();
    if (normalized !== "set-cookie" && RESPONSE_HEADERS.has(normalized)) {
      headers.append(name, value);
    }
  }

  for (const cookie of source.getSetCookie())
    headers.append("set-cookie", cookie);
  return headers;
}

function safeProblem(status: number, title: string, detail: string): Response {
  return Response.json(
    {
      type: "about:blank",
      title,
      status,
      detail,
    },
    {
      status,
      headers: {
        "cache-control": "no-store",
        "content-type": "application/problem+json",
      },
    },
  );
}

function proxySegment(segment: string): string | undefined {
  let decoded = segment;
  try {
    decoded = decodeURIComponent(segment);
  } catch {
    return undefined;
  }
  if (!decoded || decoded === "." || decoded === "..") {
    return undefined;
  }
  return encodeURIComponent(decoded);
}

function proxyPath(segments: string[] | undefined): string | undefined {
  if (!Array.isArray(segments) || segments.length === 0) {
    return undefined;
  }
  const encoded: string[] = [];
  for (const segment of segments) {
    const next = proxySegment(segment);
    if (next === undefined) return undefined;
    encoded.push(next);
  }
  return `/api/v1/${encoded.join("/")}`;
}

export async function proxyApiRequest(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  const path = proxyPath((await context.params).path);
  if (!path) {
    return safeProblem(
      400,
      "Invalid API path",
      "The requested API path is invalid.",
    );
  }

  let destination: URL;
  let clientSignal: string;
  try {
    destination = new URL(path, apiOrigin());
    clientSignal = signedClientSignal(request.headers);
  } catch {
    return safeProblem(
      503,
      "API unavailable",
      "The application API is not configured correctly.",
    );
  }
  destination.search = new URL(request.url).search;

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const headers = forwardedRequestHeaders(request.headers);
  headers.set("X-Rezumi-Client-Signal", clientSignal);
  const init: StreamingRequestInit = {
    cache: "no-store",
    headers,
    method: request.method,
    redirect: "manual",
    signal: AbortSignal.timeout(timeoutMilliseconds()),
  };
  if (hasBody && request.body) {
    init.body = request.body;
    init.duplex = "half";
  }

  try {
    const upstream = await fetch(destination, init);
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: forwardedResponseHeaders(upstream.headers),
    });
  } catch (error) {
    const timeout =
      error instanceof DOMException &&
      new Set(["AbortError", "TimeoutError"]).has(error.name);
    return safeProblem(
      timeout ? 504 : 503,
      timeout ? "API request timed out" : "API unavailable",
      timeout
        ? "The application API did not respond in time. Try again."
        : "The application API could not be reached. Try again.",
    );
  }
}
