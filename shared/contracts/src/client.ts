import createClient, { type Client } from "openapi-fetch";

import type { paths } from "./generated/schema";

export type RezumiClient = Client<paths>;

/** Create a fetch client whose paths and payloads come from FastAPI OpenAPI. */
export function createRezumiClient(baseUrl: string): RezumiClient {
  return createClient<paths>({ baseUrl });
}
