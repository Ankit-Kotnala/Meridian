export type ApiFailure = {
  message: string;
  retryAfterSeconds?: number;
  status: number;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export async function apiFailure(response: Response): Promise<ApiFailure> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = undefined;
  }

  const detail =
    isRecord(body) && typeof body.detail === "string" ? body.detail : undefined;
  const retryAfter = Number(response.headers.get("retry-after"));
  return {
    message: detail ?? "Something went wrong. Please try again.",
    ...(Number.isFinite(retryAfter) && retryAfter > 0
      ? { retryAfterSeconds: retryAfter }
      : {}),
    status: response.status,
  };
}
