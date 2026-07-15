import createClient, { type Client } from "openapi-fetch";

import type { paths } from "./generated/schema";

export type CareerOsClient = Client<paths>;

/** Create a fetch client whose paths and payloads come from FastAPI OpenAPI. */
export function createCareerOsClient(baseUrl: string): CareerOsClient {
  return createClient<paths>({ baseUrl });
}
