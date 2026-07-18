export type ApiQueryScalar = boolean | number | string;
export type ApiQueryValue =
  ApiQueryScalar | null | readonly ApiQueryScalar[] | undefined;

const MAX_KEY_LENGTH = 64;
const MAX_VALUE_LENGTH = 2_048;
const MAX_QUERY_LENGTH = 8_192;
const MAX_QUERY_VALUES = 100;
const SAFE_KEY = /^[A-Za-z][A-Za-z0-9._-]*$/;
const UNSAFE_VALUE = /[\u0000-\u001f\u007f]/;

function queryScalar(value: unknown): string {
  if (typeof value === "number") {
    if (!Number.isFinite(value))
      throw new RangeError("API query numbers must be finite");
    return String(value);
  }
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value !== "string") {
    throw new TypeError("API query values must be scalar or scalar arrays");
  }
  if (value.length > MAX_VALUE_LENGTH || UNSAFE_VALUE.test(value)) {
    throw new RangeError("API query value exceeds its safe bounds");
  }
  return value;
}

/** Build a bounded repeated-key query string for generated API parameters. */
export function buildApiQueryString(
  parameters: Readonly<Record<string, ApiQueryValue>>,
): string {
  const query = new URLSearchParams();
  let valueCount = 0;
  const entries = Object.entries(parameters);
  if (entries.length > MAX_QUERY_VALUES) {
    throw new RangeError("API query has too many parameters");
  }

  for (const [key, value] of entries) {
    if (
      key.length === 0 ||
      key.length > MAX_KEY_LENGTH ||
      !SAFE_KEY.test(key)
    ) {
      throw new TypeError("API query parameter name is invalid");
    }
    if (value === null || value === undefined) continue;
    const values = Array.isArray(value) ? value : [value];
    valueCount += values.length;
    if (valueCount > MAX_QUERY_VALUES) {
      throw new RangeError("API query has too many values");
    }
    for (const item of values) query.append(key, queryScalar(item));
  }

  const serialized = query.toString();
  if (serialized.length > MAX_QUERY_LENGTH) {
    throw new RangeError("API query exceeds its safe length");
  }
  return serialized.length > 0 ? `?${serialized}` : "";
}
