import type { paths } from "@rezumi/contracts";

declare const generatedPathBrand: unique symbol;

export type GeneratedApiPath = string & {
  readonly [generatedPathBrand]: true;
};

type PathParameterNames<Path extends string> =
  Path extends `${string}{${infer Parameter}}${infer Rest}`
    ? Parameter | PathParameterNames<Rest>
    : never;

type PathParameters<Path extends string> = Record<
  PathParameterNames<Path>,
  string
>;

/**
 * Fill a generated OpenAPI path without allowing call sites to invent endpoints.
 * Values are path-segment encoded and unresolved or unexpected parameters fail.
 */
export function fillApiPath<Path extends keyof paths & string>(
  template: Path,
  parameters: PathParameters<Path>,
): GeneratedApiPath {
  const supplied = new Set(Object.keys(parameters));
  const value = template.replaceAll(
    /{([^{}]+)}/g,
    (_match, name: string): string => {
      if (!Object.prototype.hasOwnProperty.call(parameters, name)) {
        throw new Error(`Missing API path parameter: ${name}`);
      }
      supplied.delete(name);
      const parameter = parameters[name as PathParameterNames<Path>];
      if (typeof parameter !== "string" || parameter.length === 0) {
        throw new Error(`Invalid API path parameter: ${name}`);
      }
      return encodeURIComponent(parameter);
    },
  );
  if (supplied.size > 0 || /[{}]/.test(value)) {
    throw new Error("API path parameters did not match the generated path.");
  }
  return value as GeneratedApiPath;
}
