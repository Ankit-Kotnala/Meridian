"use client";

import type { components, paths } from "@careeros/contracts";

import type { GeneratedApiPath } from "./api-path";
import { apiFailure, type ApiFailure } from "./problem-response";

export class ApiRequestError extends Error {
  readonly failure: ApiFailure;

  constructor(failure: ApiFailure) {
    super(failure.message);
    this.name = "ApiRequestError";
    this.failure = failure;
  }
}

type MutationOptions = {
  csrf: "guest" | "pre-auth" | "session";
  retryAfterRefresh?: boolean;
};

type ApiPath = keyof paths | GeneratedApiPath;

let refreshInFlight: Promise<void> | undefined;

function csrfCookie(name = "careeros_csrf"): string | undefined {
  if (typeof document === "undefined") return undefined;
  const encoded = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${name}=`))
    ?.slice(name.length + 1);
  if (!encoded) return undefined;
  try {
    return decodeURIComponent(encoded);
  } catch {
    return undefined;
  }
}

export async function getCsrfToken(): Promise<string> {
  const response = await fetch("/api/v1/auth/csrf", {
    cache: "no-store",
    credentials: "same-origin",
  });
  if (!response.ok) throw new ApiRequestError(await apiFailure(response));
  const body: unknown = await response.json();
  if (
    typeof body !== "object" ||
    body === null ||
    !("csrfToken" in body) ||
    typeof body.csrfToken !== "string"
  ) {
    throw new ApiRequestError({
      message:
        "The security token response was invalid. Refresh the page and try again.",
      status: 502,
    });
  }
  return body.csrfToken as components["schemas"]["CsrfResponse"]["csrfToken"];
}

async function refreshSessionOnce(): Promise<void> {
  const token = await getCsrfToken();
  const response = await fetch("/api/v1/auth/refresh", {
    cache: "no-store",
    credentials: "same-origin",
    headers: { "X-CSRF-Token": token },
    method: "POST",
  });
  if (!response.ok) throw new ApiRequestError(await apiFailure(response));
}

export async function refreshSession(): Promise<void> {
  refreshInFlight ??= refreshSessionOnce().finally(() => {
    refreshInFlight = undefined;
  });
  return refreshInFlight;
}

export async function apiMutation(
  path: ApiPath,
  init: Omit<RequestInit, "headers"> & { headers?: HeadersInit },
  options: MutationOptions = { csrf: "pre-auth" },
): Promise<Response> {
  async function send(forcePreAuthRefresh = false): Promise<Response> {
    const token =
      options.csrf === "pre-auth"
        ? forcePreAuthRefresh
          ? await getCsrfToken()
          : (csrfCookie() ?? (await getCsrfToken()))
        : options.csrf === "guest"
          ? csrfCookie("careeros_guest_csrf")
          : csrfCookie();
    if (!token) {
      throw new ApiRequestError({
        message: "Your secure session could not be confirmed. Sign in again.",
        status: 401,
      });
    }
    const headers = new Headers(init.headers);
    headers.set(
      options.csrf === "guest" ? "X-Guest-CSRF" : "X-CSRF-Token",
      token,
    );
    if (init.body) headers.set("content-type", "application/json");
    return fetch(path, {
      ...init,
      cache: "no-store",
      credentials: "same-origin",
      headers,
    });
  }

  let response = await send();
  if (response.status === 403 && options.csrf === "pre-auth") {
    response = await send(true);
  }
  if (
    response.status === 401 &&
    options.csrf === "session" &&
    options.retryAfterRefresh !== false
  ) {
    await refreshSession();
    response = await send();
  }
  if (!response.ok) throw new ApiRequestError(await apiFailure(response));
  return response;
}

export async function apiQuery(
  path: keyof paths | GeneratedApiPath,
  options: { retryAfterRefresh?: boolean; signal?: AbortSignal } = {},
): Promise<Response> {
  const send = () =>
    fetch(path, {
      cache: "no-store",
      credentials: "same-origin",
      ...(options.signal ? { signal: options.signal } : {}),
    });
  let response = await send();
  if (response.status === 401 && options.retryAfterRefresh !== false) {
    await refreshSession();
    response = await send();
  }
  if (!response.ok) throw new ApiRequestError(await apiFailure(response));
  return response;
}

export function requestErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof ApiRequestError)) return fallback;
  if (error.failure.status === 429) {
    const wait = error.failure.retryAfterSeconds;
    return wait
      ? `Too many attempts. Try again in ${wait} seconds.`
      : "Too many attempts. Wait a moment and try again.";
  }
  return error.failure.message || fallback;
}
