/** Public API types are aliases over the generated OpenAPI schema. */

export { createCareerOsClient } from "./client";
export type { CareerOsClient } from "./client";
export type { components, operations, paths } from "./generated/schema";

import type { components } from "./generated/schema";

export type ComponentReadiness = components["schemas"]["ComponentReadiness"];
export type HealthResponse = components["schemas"]["HealthResponse"];
export type MetaResponse = components["schemas"]["MetaResponse"];
export type ReadinessResponse = components["schemas"]["ReadinessResponse"];
