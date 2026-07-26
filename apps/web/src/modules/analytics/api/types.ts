import type { components } from "@careeros/contracts";

export type AnalyticsScope =
  components["schemas"]["AnalyticsRefreshRequest"]["scope"];
export type AnalyticsRefreshInput =
  components["schemas"]["AnalyticsRefreshRequest"];
export type AnalyticsRefresh =
  components["schemas"]["AnalyticsRefreshResponse"] & {
    windowEnd: string;
    windowStart: string;
  };
export type AnalyticsReport = components["schemas"]["AnalyticsReportResponse"];
export type AnalyticsPayload =
  components["schemas"]["AnalyticsPayloadResponse"];
export type AnalyticsRate = components["schemas"]["AnalyticsRateResponse"];
export type AnalyticsTimeBucket =
  components["schemas"]["AnalyticsTimeBucketResponse"];
export type ReadinessHistory =
  components["schemas"]["ReadinessHistoryResponse"];
export type RequirementCoverageTrend =
  components["schemas"]["RequirementCoverageTrendResponse"];
export type ResumeVersionOutcomePerformance =
  components["schemas"]["ResumeVersionOutcomePerformanceResponse"];
export type AnalyticsMetricDefinition =
  components["schemas"]["AnalyticsMetricDefinitionResponse"];
