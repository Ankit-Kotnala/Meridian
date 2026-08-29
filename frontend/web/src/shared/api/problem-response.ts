export type ApiFieldFailure = {
  code: string;
  field: string;
  message: string;
};

export type ApiFailure = {
  code?: string;
  errors?: ApiFieldFailure[];
  message: string;
  requestId?: string;
  retryAfterSeconds?: number;
  status: number;
};

const FALLBACK_MESSAGE = "Something went wrong. Please try again.";
const MAX_DETAIL_LENGTH = 1_000;
const MAX_ERROR_COUNT = 20;
const MAX_ERROR_CODE_LENGTH = 80;
const MAX_ERROR_FIELD_LENGTH = 200;
const MAX_ERROR_MESSAGE_LENGTH = 500;
const MAX_REQUEST_ID_LENGTH = 128;
const MAX_RETRY_AFTER_SECONDS = 86_400;
const SAFE_CODE = /^[a-z][a-z0-9_]*$/;
const SAFE_REQUEST_ID = /^[A-Za-z0-9._-]+$/;
const UNSAFE_TEXT = /[\u0000-\u001f\u007f\u202a-\u202e\u2066-\u2069]/;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function boundedText(
  value: unknown,
  maximumLength: number,
): string | undefined {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value.length > maximumLength ||
    UNSAFE_TEXT.test(value)
  ) {
    return undefined;
  }
  return value;
}

function problemCode(value: unknown): string | undefined {
  const code = boundedText(value, MAX_ERROR_CODE_LENGTH);
  return code && SAFE_CODE.test(code) ? code : undefined;
}

function problemErrors(value: unknown): ApiFieldFailure[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const errors = value.slice(0, MAX_ERROR_COUNT).flatMap((candidate) => {
    if (!isRecord(candidate)) return [];
    const code = problemCode(candidate.code);
    const field = boundedText(candidate.field, MAX_ERROR_FIELD_LENGTH);
    const message = boundedText(candidate.message, MAX_ERROR_MESSAGE_LENGTH);
    return code && field && message ? [{ code, field, message }] : [];
  });
  return errors.length > 0 ? errors : undefined;
}

function problemRequestId(
  body: unknown,
  response: Response,
): string | undefined {
  const bodyRequestId = isRecord(body) ? body.requestId : undefined;
  const safeRequestId = (value: unknown) => {
    const candidate = boundedText(value, MAX_REQUEST_ID_LENGTH);
    return candidate && SAFE_REQUEST_ID.test(candidate) ? candidate : undefined;
  };
  return (
    safeRequestId(bodyRequestId) ??
    safeRequestId(response.headers.get("x-request-id"))
  );
}

function retryAfterSeconds(value: string | null): number | undefined {
  if (value === null || !/^[0-9]{1,10}$/.test(value)) return undefined;
  const seconds = Number(value);
  return Number.isSafeInteger(seconds) &&
    seconds > 0 &&
    seconds <= MAX_RETRY_AFTER_SECONDS
    ? seconds
    : undefined;
}

export async function apiFailure(response: Response): Promise<ApiFailure> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = undefined;
  }

  const detail = isRecord(body)
    ? boundedText(body.detail, MAX_DETAIL_LENGTH)
    : undefined;
  const code = isRecord(body) ? problemCode(body.code) : undefined;
  const errors = isRecord(body) ? problemErrors(body.errors) : undefined;
  const requestId = problemRequestId(body, response);
  const retryAfter = retryAfterSeconds(response.headers.get("retry-after"));
  return {
    ...(code ? { code } : {}),
    ...(errors ? { errors } : {}),
    message: detail ?? FALLBACK_MESSAGE,
    ...(requestId ? { requestId } : {}),
    ...(retryAfter ? { retryAfterSeconds: retryAfter } : {}),
    status: response.status,
  };
}
