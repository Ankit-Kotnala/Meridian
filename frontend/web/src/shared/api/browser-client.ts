"use client";

import { createRezumiClient } from "@rezumi/contracts";

/** The browser uses generated API paths through the same-origin Next proxy. */
export function createBrowserApiClient() {
  return createRezumiClient("");
}

export function csrfToken(): string | undefined {
  const prefix = "rezumi_csrf=";
  for (const part of document.cookie.split(";")) {
    const value = part.trim();
    if (value.startsWith(prefix))
      return decodeURIComponent(value.slice(prefix.length));
  }
  return undefined;
}

export function csrfHeaders(): HeadersInit {
  const token = csrfToken();
  return token ? { "X-CSRF-Token": token } : {};
}
