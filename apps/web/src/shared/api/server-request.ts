import { cookies } from "next/headers";

import type { paths } from "@careeros/contracts";

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

export async function serverApiFetch(
  path: keyof paths | GeneratedApiPath,
): Promise<Response> {
  const store = await cookies();
  const cookieHeader = ["careeros_session", "careeros_refresh", "careeros_csrf"]
    .map((name) => store.get(name))
    .filter((cookie) => cookie !== undefined)
    .map((cookie) => `${cookie.name}=${cookie.value}`)
    .join("; ");

  const init: RequestInit = {
    cache: "no-store",
  };
  if (cookieHeader) init.headers = { cookie: cookieHeader };
  return fetch(`${serverApiOrigin()}${path}`, init);
}
