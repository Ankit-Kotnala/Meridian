import type { components } from "@rezumi/contracts";
import { describe, expectTypeOf, it } from "vitest";

import type {
  AnalyticsMetricDefinition,
  AnalyticsPayload,
  AnalyticsRefresh,
  AnalyticsReport,
  RequirementCoverageTrend,
  ResumeVersionOutcomePerformance,
} from "../api/types";

describe("Career Analytics generated contract aliases", () => {
  it("keeps every wire type exactly equal to the generated OpenAPI contract", () => {
    expectTypeOf<AnalyticsRefresh>().toMatchTypeOf<
      components["schemas"]["AnalyticsRefreshResponse"]
    >();
    expectTypeOf<AnalyticsRefresh["windowStart"]>().toEqualTypeOf<string>();
    expectTypeOf<AnalyticsRefresh["windowEnd"]>().toEqualTypeOf<string>();
    expectTypeOf<AnalyticsReport>().toEqualTypeOf<
      components["schemas"]["AnalyticsReportResponse"]
    >();
    expectTypeOf<AnalyticsPayload>().toEqualTypeOf<
      components["schemas"]["AnalyticsPayloadResponse"]
    >();
    expectTypeOf<AnalyticsMetricDefinition>().toEqualTypeOf<
      components["schemas"]["AnalyticsMetricDefinitionResponse"]
    >();
    expectTypeOf<RequirementCoverageTrend>().toEqualTypeOf<
      components["schemas"]["RequirementCoverageTrendResponse"]
    >();
    expectTypeOf<ResumeVersionOutcomePerformance>().toEqualTypeOf<
      components["schemas"]["ResumeVersionOutcomePerformanceResponse"]
    >();
  });
});
