import { cookies } from "next/headers";

import type { paths } from "@rezumi/contracts";

import type { GeneratedApiPath } from "./api-path";

function serverApiOrigin(): string {
  const value = new URL(process.env.API_BASE_URL ?? "http://127.0.0.1:8000");
  if (
    !new Set(["http:", "https:"]).has(value.protocol) ||
    value.pathname !== "/" ||
    value.username ||
    value.password
  ) {
    throw new Error("API_BASE_URL must be a valid HTTP(S) origin.");
  }
  return value.origin;
}

/**
 * Server reads are bounded so one unresponsive dependency cannot hold a page
 * open indefinitely. Callers already degrade a failed read into an explicit
 * "unavailable" state, and an aborted read reaches them on that same path, so a
 * stalled section renders as unavailable instead of stalling the whole route.
 */
const SERVER_READ_TIMEOUT_MS = 8_000;

export async function serverApiFetch(
  path: keyof paths | GeneratedApiPath,
  timeoutMs: number = SERVER_READ_TIMEOUT_MS,
): Promise<Response> {
  const store = await cookies();
  const cookieHeader = ["rezumi_session", "rezumi_refresh", "rezumi_csrf"]
    .map((name) => store.get(name))
    .filter((cookie) => cookie !== undefined)
    .map((cookie) => `${cookie.name}=${cookie.value}`)
    .join("; ");

  const init: RequestInit = {
    cache: "no-store",
    signal: AbortSignal.timeout(timeoutMs),
  };
  if (cookieHeader) init.headers = { cookie: cookieHeader };
  return fetch(`${serverApiOrigin()}${path}`, init);
}
