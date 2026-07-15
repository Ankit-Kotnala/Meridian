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

function proxyPath(segments: string[]): string | undefined {
  if (
    segments.length === 0 ||
    segments.some(
      (segment) =>
        !segment ||
        segment === "." ||
        segment === ".." ||
        segment.includes("/"),
    )
  ) {
    return undefined;
  }
  return `/api/v1/${segments.map(encodeURIComponent).join("/")}`;
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
  try {
    destination = new URL(path, apiOrigin());
  } catch {
    return safeProblem(
      503,
      "API unavailable",
      "The application API is not configured correctly.",
    );
  }
  destination.search = new URL(request.url).search;

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const init: StreamingRequestInit = {
    cache: "no-store",
    headers: forwardedRequestHeaders(request.headers),
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
