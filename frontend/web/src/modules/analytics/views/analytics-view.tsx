"use client";

import {
  BarChart3,
  CalendarRange,
  Clock3,
  Database,
  RefreshCcw,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Input,
  LoadingSkeleton,
  PageHeader,
  Select,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  getAnalyticsRefresh,
  getAnalyticsReport,
  requestAnalyticsRefresh,
} from "../api/analytics-api";
import type {
  AnalyticsRate,
  AnalyticsRefresh,
  AnalyticsReport,
  AnalyticsScope,
  RequirementCoverageTrend,
  ResumeVersionOutcomePerformance,
} from "../api/types";

export const NON_CAUSAL_INTERPRETATION =
  "These analytics describe correlations and observed patterns only. They do not establish causation, predict hiring decisions, or promise career outcomes.";

const SCORING_DISCLAIMER =
  "Meridian scores are internal readiness measurements. They are not scores provided by an employer or applicant tracking system and do not guarantee interviews or employment outcomes.";

type AnalyticsFilters = {
  scope: AnalyticsScope;
  timezone: string;
  windowEnd: string;
  windowStart: string;
};

const scopes: Array<{
  description: string;
  label: string;
  value: AnalyticsScope;
}> = [
  {
    description: "Applications, outcomes, achievements, and readiness",
    label: "Overview",
    value: "overview",
  },
  {
    description: "Application activity and observed funnel outcomes",
    label: "Applications",
    value: "applications",
  },
  {
    description: "Role-readiness history and maintenance",
    label: "Readiness",
    value: "readiness",
  },
];

export function calendarDateInTimezone(now: Date, timezone: string): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    calendar: "iso8601",
    day: "2-digit",
    month: "2-digit",
    numberingSystem: "latn",
    timeZone: timezone,
    year: "numeric",
  }).formatToParts(now);
  const value = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value;
  const year = value("year");
  const month = value("month");
  const day = value("day");
  if (!year || !month || !day) {
    throw new Error("The local analytics calendar date could not be resolved.");
  }
  return `${year}-${month}-${day}`;
}

function previousCalendarYear(value: string): string {
  const [yearValue, monthValue, dayValue] = value
    .split("-")
    .map((part) => Number(part));
  if (!yearValue || !monthValue || !dayValue) {
    throw new Error("The analytics calendar date is invalid.");
  }
  const year = yearValue - 1;
  const finalDay = Math.min(
    dayValue,
    new Date(Date.UTC(year, monthValue, 0)).getUTCDate(),
  );
  return [
    year.toString().padStart(4, "0"),
    monthValue.toString().padStart(2, "0"),
    finalDay.toString().padStart(2, "0"),
  ].join("-");
}

export function defaultAnalyticsWindow(
  now = new Date(),
  timezone = resolvedTimezone(),
): AnalyticsFilters {
  const windowEnd = calendarDateInTimezone(now, timezone);
  return {
    scope: "overview",
    timezone,
    windowEnd,
    windowStart: previousCalendarYear(windowEnd),
  };
}

function resolvedTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

function humanize(value: string): string {
  return value
    .replaceAll(/([a-z0-9])([A-Z])/g, "$1 $2")
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formattedDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(new Date(`${value.slice(0, 10)}T12:00:00Z`));
}

function formattedDateTime(value: string | null): string {
  if (!value) return "Not available";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function analyticsFilterSignature(filters: AnalyticsFilters): string {
  return JSON.stringify([
    filters.scope,
    filters.timezone,
    filters.windowStart,
    filters.windowEnd,
  ]);
}

function refreshMatchesFilters(
  refresh: AnalyticsRefresh,
  filters: AnalyticsFilters,
): boolean {
  return (
    analyticsFilterSignature({
      scope: refresh.scope,
      timezone: refresh.timezone,
      windowEnd: refresh.windowEnd,
      windowStart: refresh.windowStart,
    }) === analyticsFilterSignature(filters)
  );
}

function isFilterBoundRefresh(
  refresh: AnalyticsReport["refresh"],
): refresh is AnalyticsRefresh {
  return (
    refresh !== null &&
    typeof refresh === "object" &&
    "windowStart" in refresh &&
    typeof refresh.windowStart === "string" &&
    "windowEnd" in refresh &&
    typeof refresh.windowEnd === "string"
  );
}

function intentKey(filters: AnalyticsFilters): string {
  const random =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `analytics.${filters.scope}.${filters.windowStart}.${filters.windowEnd}.${random}`;
}

function rateValue(rate: AnalyticsRate): string {
  if (rate.suppressed) return "Suppressed (<5 observations)";
  if (rate.valueBasisPoints === null || rate.valueBasisPoints === undefined) {
    return "Not available";
  }
  return `${(rate.valueBasisPoints / 100).toFixed(1)}%`;
}

function freshnessTone(
  freshness: AnalyticsReport["freshness"],
): "danger" | "neutral" | "primary" | "success" | "warning" {
  if (freshness === "current") return "success";
  if (freshness === "refreshing") return "primary";
  if (freshness === "stale") return "warning";
  if (freshness === "failed") return "danger";
  return "neutral";
}

function SectionHeading({
  children,
  icon,
  id,
}: {
  children: ReactNode;
  icon: ReactNode;
  id: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <span
        aria-hidden="true"
        className="grid size-9 place-items-center rounded-xl bg-primary-soft text-primary"
      >
        {icon}
      </span>
      <h2 className="text-xl font-black" id={id}>
        {children}
      </h2>
    </div>
  );
}

function CountsTable({ counts }: { counts: Record<string, number> }) {
  const entries = Object.entries(counts).sort(([left], [right]) =>
    left.localeCompare(right),
  );
  if (entries.length === 0) {
    return (
      <p className="mt-3 text-sm text-muted">No count metrics available.</p>
    );
  }
  return (
    <div className="data-region table-scroll mt-3">
      <table className="min-w-full divide-y divide-line text-left text-sm">
        <caption className="sr-only">
          Observed counts in the selected analytics window
        </caption>
        <thead className="bg-surface-subtle text-xs uppercase tracking-wide text-muted">
          <tr>
            <th className="px-4 py-3" scope="col">
              Observed metric
            </th>
            <th className="px-4 py-3" scope="col">
              Count
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {entries.map(([key, count]) => (
            <tr key={key}>
              <th className="px-4 py-3 font-bold" scope="row">
                {humanize(key)}
              </th>
              <td className="px-4 py-3 tabular-nums">{count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RatesTable({ rates }: { rates: Record<string, AnalyticsRate> }) {
  const entries = Object.entries(rates).sort(([left], [right]) =>
    left.localeCompare(right),
  );
  if (entries.length === 0) {
    return (
      <p className="mt-3 text-sm text-muted">No rate metrics available.</p>
    );
  }
  return (
    <div className="data-region table-scroll mt-3">
      <table className="min-w-full divide-y divide-line text-left text-sm">
        <caption className="sr-only">
          Observed rates; small cohorts are suppressed for privacy
        </caption>
        <thead className="bg-surface-subtle text-xs uppercase tracking-wide text-muted">
          <tr>
            <th className="px-4 py-3" scope="col">
              Observed rate
            </th>
            <th className="px-4 py-3" scope="col">
              Value
            </th>
            <th className="px-4 py-3" scope="col">
              Eligible observations
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {entries.map(([key, rate]) => (
            <tr key={key}>
              <th className="px-4 py-3 font-bold" scope="row">
                {humanize(key)}
              </th>
              <td className="px-4 py-3">
                {rate.suppressed ? (
                  <span className="font-bold text-muted">
                    {rateValue(rate)}
                  </span>
                ) : (
                  <span className="tabular-nums">{rateValue(rate)}</span>
                )}
              </td>
              <td className="px-4 py-3 text-muted">
                {rate.suppressed
                  ? (rate.suppressionReason ??
                    "Hidden because the denominator is below 5.")
                  : rate.denominator === null || rate.denominator === undefined
                    ? "Not available"
                    : `${rate.numerator ?? 0} of ${rate.denominator}`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CoverageTrendTable({
  values,
}: {
  values: RequirementCoverageTrend[];
}) {
  if (values.length === 0) return null;
  return (
    <div className="data-region table-scroll mt-3">
      <table className="min-w-full divide-y divide-line text-left text-sm">
        <caption className="sr-only">
          Requirement coverage trend; small samples are suppressed
        </caption>
        <thead className="bg-surface-subtle text-xs uppercase tracking-wide text-muted">
          <tr>
            <th className="px-4 py-3" scope="col">
              Period
            </th>
            <th className="px-4 py-3" scope="col">
              Average grounded coverage
            </th>
            <th className="px-4 py-3" scope="col">
              Eligible observations
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {values.map((value) => (
            <tr key={`${value.start}-${value.end}`}>
              <th className="whitespace-nowrap px-4 py-3 font-bold" scope="row">
                {formattedDate(value.start)} – {formattedDate(value.end)}
              </th>
              <td className="px-4 py-3">
                {value.suppressed || value.valueBasisPoints === null
                  ? "Suppressed (<5 observations)"
                  : `${(value.valueBasisPoints / 100).toFixed(1)}%`}
              </td>
              <td className="px-4 py-3 text-muted">
                {value.suppressed
                  ? (value.suppressionReason ??
                    "Hidden because the denominator is below 5.")
                  : (value.sampleSize ?? "Not available")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ResumeVersionOutcomeTable({
  values,
}: {
  values: ResumeVersionOutcomePerformance[];
}) {
  if (values.length === 0) return null;
  return (
    <div className="data-region table-scroll mt-3">
      <table className="min-w-full divide-y divide-line text-left text-sm">
        <caption className="sr-only">
          Observed outcomes segmented by exact immutable resume version
        </caption>
        <thead className="bg-surface-subtle text-xs uppercase tracking-wide text-muted">
          <tr>
            <th className="px-4 py-3" scope="col">
              Resume version
            </th>
            <th className="px-4 py-3" scope="col">
              Applications
            </th>
            <th className="px-4 py-3" scope="col">
              Response rate
            </th>
            <th className="px-4 py-3" scope="col">
              Interview rate
            </th>
            <th className="px-4 py-3" scope="col">
              Offer rate
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {values.map((value) => (
            <tr key={value.resumeVersionId}>
              <th className="px-4 py-3 font-bold" scope="row">
                Version {value.resumeVersionNumber}
                <span className="sr-only"> {value.resumeVersionId}</span>
              </th>
              <td className="px-4 py-3 tabular-nums">
                {value.applicationCount}
              </td>
              <td className="px-4 py-3">{rateValue(value.responseRate)}</td>
              <td className="px-4 py-3">{rateValue(value.interviewRate)}</td>
              <td className="px-4 py-3">{rateValue(value.offerRate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BreakdownTables({
  breakdowns,
}: {
  breakdowns: Record<string, Array<{ count: number; key: string }>>;
}) {
  const entries = Object.entries(breakdowns).sort(([left], [right]) =>
    left.localeCompare(right),
  );
  if (entries.length === 0) {
    return (
      <EmptyState
        className="mt-3"
        description="Dimension summaries will appear after eligible activity is recorded."
        title="No dimension breakdowns"
      />
    );
  }
  return (
    <div className="mt-3 grid gap-4 lg:grid-cols-2">
      {entries.map(([dimension, values]) => (
        <div className="data-region table-scroll" key={dimension}>
          <table className="min-w-full divide-y divide-line text-left text-sm">
            <caption className="bg-surface-subtle px-4 py-3 text-left font-semibold text-foreground">
              {humanize(dimension)}
            </caption>
            <thead className="bg-surface-subtle text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-2" scope="col">
                  Category
                </th>
                <th className="px-4 py-2" scope="col">
                  Count
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {values.map((value) => (
                <tr key={`${dimension}-${value.key}`}>
                  <th className="px-4 py-3 font-bold" scope="row">
                    {value.key === "other" ? "Other categories" : value.key}
                  </th>
                  <td className="px-4 py-3 tabular-nums">{value.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

function ReportContent({ report }: { report: AnalyticsReport }) {
  const payload = report.payload;
  if (!payload) {
    return (
      <EmptyState
        description={
          report.freshness === "failed"
            ? "The latest refresh did not produce a usable report. Retry the refresh after reviewing the status."
            : "Refresh this window to create a purpose-limited analytics snapshot."
        }
        title={
          report.freshness === "failed"
            ? "No current report is available"
            : "No analytics snapshot yet"
        }
      />
    );
  }
  return (
    <div className="space-y-8">
      <section aria-labelledby="analytics-counts">
        <SectionHeading
          icon={<BarChart3 className="size-4" />}
          id="analytics-counts"
        >
          Observed activity
        </SectionHeading>
        <p className="mt-2 text-sm leading-6 text-muted">
          Counts and rates cover only the selected window. A rate with fewer
          than five eligible observations is hidden.
        </p>
        <div className="grid gap-4 lg:grid-cols-2">
          <CountsTable counts={payload.counts} />
          <RatesTable rates={payload.rates} />
        </div>
      </section>

      <section aria-labelledby="analytics-breakdowns">
        <SectionHeading
          icon={<Database className="size-4" />}
          id="analytics-breakdowns"
        >
          Top dimensions
        </SectionHeading>
        <p className="mt-2 text-sm leading-6 text-muted">
          Each dimension is bounded to its leading categories; the remaining
          categories are grouped as Other.
        </p>
        <BreakdownTables breakdowns={payload.breakdowns} />
      </section>

      {payload.requirementCoverageTrend.length > 0 && (
        <section aria-labelledby="analytics-coverage-trend">
          <SectionHeading
            icon={<TrendingUp className="size-4" />}
            id="analytics-coverage-trend"
          >
            Requirement coverage trend
          </SectionHeading>
          <p className="mt-2 text-sm leading-6 text-muted">
            Coverage is computed from grounded requirements pinned to each
            application. Averages with fewer than five observations are hidden.
          </p>
          <CoverageTrendTable values={payload.requirementCoverageTrend} />
        </section>
      )}

      {payload.outcomesByResumeVersion.length > 0 && (
        <section aria-labelledby="analytics-resume-outcomes">
          <SectionHeading
            icon={<Database className="size-4" />}
            id="analytics-resume-outcomes"
          >
            Outcomes by immutable resume version
          </SectionHeading>
          <p className="mt-2 text-sm leading-6 text-muted">
            These are observed correlations for the exact resume version pinned
            to each application. They cannot be interpreted as causal evidence.
          </p>
          <ResumeVersionOutcomeTable values={payload.outcomesByResumeVersion} />
        </section>
      )}

      <section aria-labelledby="analytics-time">
        <SectionHeading
          icon={<CalendarRange className="size-4" />}
          id="analytics-time"
        >
          Activity over time
        </SectionHeading>
        {payload.timeBuckets.length === 0 ? (
          <p className="mt-3 text-sm text-muted">
            No time-bucket activity in this window.
          </p>
        ) : (
          <div className="data-region table-scroll mt-3">
            <table className="min-w-full divide-y divide-line text-left text-sm">
              <caption className="sr-only">
                Applications, interviews, offers, and achievements by time
                bucket
              </caption>
              <thead className="bg-surface-subtle text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="px-4 py-3" scope="col">
                    Period
                  </th>
                  <th className="px-4 py-3" scope="col">
                    Applications
                  </th>
                  <th className="px-4 py-3" scope="col">
                    Interviews
                  </th>
                  <th className="px-4 py-3" scope="col">
                    Offers
                  </th>
                  <th className="px-4 py-3" scope="col">
                    Achievements
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {payload.timeBuckets.map((bucket) => (
                  <tr key={`${bucket.start}-${bucket.end}`}>
                    <th
                      className="whitespace-nowrap px-4 py-3 font-bold"
                      scope="row"
                    >
                      {formattedDate(bucket.start)} –{" "}
                      {formattedDate(bucket.end)}
                    </th>
                    <td className="px-4 py-3 tabular-nums">
                      {bucket.applications}
                    </td>
                    <td className="px-4 py-3 tabular-nums">
                      {bucket.interviews}
                    </td>
                    <td className="px-4 py-3 tabular-nums">{bucket.offers}</td>
                    <td className="px-4 py-3 tabular-nums">
                      {bucket.achievements}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section aria-labelledby="analytics-readiness">
        <SectionHeading
          icon={<TrendingUp className="size-4" />}
          id="analytics-readiness"
        >
          Readiness history
        </SectionHeading>
        <p className="mt-2 max-w-3xl text-xs font-semibold leading-5 text-muted">
          {SCORING_DISCLAIMER}
        </p>
        {payload.readinessHistory.length === 0 ? (
          <p className="mt-3 text-sm text-muted">
            No readiness analyses in this window.
          </p>
        ) : (
          <div className="data-region table-scroll mt-3">
            <table className="min-w-full divide-y divide-line text-left text-sm">
              <caption className="sr-only">
                Internal role-readiness measurements over time
              </caption>
              <thead className="bg-surface-subtle text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="px-4 py-3" scope="col">
                    Created
                  </th>
                  <th className="px-4 py-3" scope="col">
                    Role
                  </th>
                  <th className="px-4 py-3" scope="col">
                    Internal readiness
                  </th>
                  <th className="px-4 py-3" scope="col">
                    Label
                  </th>
                  <th className="px-4 py-3" scope="col">
                    Engine
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {payload.readinessHistory.map((entry) => (
                  <tr key={entry.analysisId}>
                    <td className="whitespace-nowrap px-4 py-3">
                      {formattedDateTime(entry.createdAt)}
                    </td>
                    <th className="px-4 py-3 font-bold" scope="row">
                      {entry.roleLabel}
                    </th>
                    <td className="px-4 py-3 tabular-nums">
                      {entry.rawScoreBasisPoints === null
                        ? "Insufficient data"
                        : `${(entry.rawScoreBasisPoints / 100).toFixed(1)}%`}
                    </td>
                    <td className="px-4 py-3">{humanize(entry.label)}</td>
                    <td className="px-4 py-3 text-muted">
                      {entry.engineVersion}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function Watermarks({ report }: { report: AnalyticsReport }) {
  const values = Object.values(report.sourceWatermarks).sort((left, right) =>
    left.source.localeCompare(right.source),
  );
  return (
    <details className="rounded-xl border border-line p-4">
      <summary className="cursor-pointer font-extrabold">
        Source completeness watermarks ({values.length})
      </summary>
      <p className="mt-2 text-xs leading-5 text-muted">
        A report is current only when its complete source snapshot still matches
        these recorded watermarks.
      </p>
      {values.length === 0 ? (
        <p className="mt-3 text-sm text-muted">
          No source watermarks are available.
        </p>
      ) : (
        <div className="data-region table-scroll mt-3">
          <table className="min-w-full divide-y divide-line text-left text-sm">
            <caption className="sr-only">
              Source record counts and completeness watermark times
            </caption>
            <thead className="text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-3 py-2" scope="col">
                  Source
                </th>
                <th className="px-3 py-2" scope="col">
                  Records
                </th>
                <th className="px-3 py-2" scope="col">
                  Latest source update
                </th>
                <th className="px-3 py-2" scope="col">
                  Watermark
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {values.map((watermark) => (
                <tr key={watermark.source}>
                  <th className="px-3 py-2 font-bold" scope="row">
                    {humanize(watermark.source)}
                  </th>
                  <td className="px-3 py-2 tabular-nums">
                    {watermark.recordCount}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">
                    {formattedDateTime(watermark.maxUpdatedAt)}
                  </td>
                  <td
                    className="max-w-44 truncate px-3 py-2 font-mono text-xs text-muted"
                    title={watermark.token}
                  >
                    {watermark.token.slice(0, 18)}…
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </details>
  );
}

function MetricSemantics({ report }: { report: AnalyticsReport }) {
  const definitions = report.metricDefinitions;
  const timestamps = Object.entries(report.timestampSemantics).sort(
    ([left], [right]) => left.localeCompare(right),
  );
  return (
    <details className="rounded-xl border border-line p-4">
      <summary className="cursor-pointer font-extrabold">
        Metric, cohort, and timestamp definitions
      </summary>
      <p className="mt-3 text-sm leading-6">
        <strong>Application cohort:</strong> {report.cohortDefinition}
      </p>
      <p className="mt-2 text-sm leading-6">
        <strong>Suppression policy:</strong>{" "}
        {report.suppressionPolicy.appliesTo} Minimum denominator{" "}
        {report.suppressionPolicy.minimumDenominator}.{" "}
        {report.suppressionPolicy.reason}
      </p>
      {definitions.length > 0 && (
        <div className="data-region table-scroll mt-3">
          <table className="min-w-full divide-y divide-line text-left text-sm">
            <caption className="sr-only">
              Versioned Career Analytics metric definitions
            </caption>
            <thead className="text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-3 py-2" scope="col">
                  Metric
                </th>
                <th className="px-3 py-2" scope="col">
                  Definition
                </th>
                <th className="px-3 py-2" scope="col">
                  Event timestamp
                </th>
                <th className="px-3 py-2" scope="col">
                  Version
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {definitions.map((definition) => (
                <tr key={definition.key}>
                  <th className="px-3 py-2 font-bold" scope="row">
                    {humanize(definition.key)}
                  </th>
                  <td className="px-3 py-2">{definition.description}</td>
                  <td className="px-3 py-2">{definition.eventTimestamp}</td>
                  <td className="px-3 py-2 font-mono text-xs">
                    {definition.version}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {timestamps.length > 0 && (
        <dl className="mt-3 grid gap-2 text-sm">
          {timestamps.map(([key, value]) => (
            <div key={key}>
              <dt className="inline font-bold">{humanize(key)}: </dt>
              <dd className="inline text-muted">{value}</dd>
            </div>
          ))}
        </dl>
      )}
    </details>
  );
}

function RefreshStatus({ refresh }: { refresh: AnalyticsRefresh }) {
  const terminal =
    refresh.status === "completed" || refresh.status === "dead_letter";
  return (
    <Alert
      title={
        terminal
          ? "Analytics refresh finished"
          : "Analytics refresh in progress"
      }
      tone={refresh.status === "dead_letter" ? "danger" : "info"}
    >
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Badge
          tone={
            refresh.status === "completed"
              ? "success"
              : refresh.status === "dead_letter"
                ? "danger"
                : "primary"
          }
        >
          {humanize(refresh.status)}
        </Badge>
        <span>
          Attempt {refresh.attempts} of {refresh.maxAttempts}
        </span>
        {refresh.safeErrorCode && (
          <span className="text-muted">Code: {refresh.safeErrorCode}</span>
        )}
      </div>
    </Alert>
  );
}

export function AnalyticsView() {
  const initialFilters = useMemo(() => defaultAnalyticsWindow(), []);
  const [filters, setFilters] = useState(initialFilters);
  const [appliedFilters, setAppliedFilters] = useState(initialFilters);
  const [report, setReport] = useState<AnalyticsReport>();
  const [refresh, setRefresh] = useState<AnalyticsRefresh>();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [pollFailureCount, setPollFailureCount] = useState(0);
  const [failure, setFailure] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const reportEpoch = useRef(0);
  const reportController = useRef<AbortController | undefined>(undefined);
  const pollingController = useRef<AbortController | undefined>(undefined);
  const refreshController = useRef<AbortController | undefined>(undefined);
  const filterEpoch = useRef(0);
  const appliedSignature = useRef(analyticsFilterSignature(initialFilters));
  const refreshInFlight = useRef<string | undefined>(undefined);
  const refreshIntent = useRef<{ key: string; signature: string } | undefined>(
    undefined,
  );

  const load = useCallback(async (next: AnalyticsFilters) => {
    reportController.current?.abort();
    const controller = new AbortController();
    reportController.current = controller;
    const epoch = ++reportEpoch.current;
    const signature = analyticsFilterSignature(next);
    setLoading(true);
    setFailure(undefined);
    try {
      const result = await getAnalyticsReport(next, controller.signal);
      if (
        controller.signal.aborted ||
        epoch !== reportEpoch.current ||
        appliedSignature.current !== signature
      ) {
        return;
      }
      setPollFailureCount(0);
      setReport(result);
      setRefresh(
        isFilterBoundRefresh(result.refresh) &&
          refreshMatchesFilters(result.refresh, next)
          ? result.refresh
          : undefined,
      );
    } catch (error) {
      if (
        controller.signal.aborted ||
        epoch !== reportEpoch.current ||
        appliedSignature.current !== signature ||
        isAbortError(error)
      ) {
        return;
      }
      setFailure(requestErrorMessage(error, "Analytics could not be loaded."));
    } finally {
      if (
        !controller.signal.aborted &&
        epoch === reportEpoch.current &&
        appliedSignature.current === signature
      ) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void load(appliedFilters));
    return () => {
      reportEpoch.current += 1;
      reportController.current?.abort();
    };
  }, [appliedFilters, load]);

  useEffect(() => {
    if (
      !refresh ||
      refresh.status === "completed" ||
      refresh.status === "dead_letter"
    ) {
      return;
    }
    const controller = new AbortController();
    pollingController.current?.abort();
    pollingController.current = controller;
    const signature = analyticsFilterSignature(appliedFilters);
    const epoch = filterEpoch.current;
    if (
      appliedSignature.current !== signature ||
      !refreshMatchesFilters(refresh, appliedFilters)
    ) {
      return;
    }
    if (pollFailureCount >= 5) return;
    const delay = Math.min(1200 * 2 ** pollFailureCount, 10_000);
    const timer = window.setTimeout(() => {
      void getAnalyticsRefresh(refresh.id, controller.signal)
        .then((next) => {
          if (
            controller.signal.aborted ||
            epoch !== filterEpoch.current ||
            appliedSignature.current !== signature ||
            !refreshMatchesFilters(next, appliedFilters)
          ) {
            return;
          }
          setPollFailureCount(0);
          setFailure(undefined);
          setRefresh(next);
          if (next.status === "completed") {
            setSuccess("Analytics refresh completed.");
            void load(appliedFilters);
          } else if (next.status === "dead_letter") {
            setFailure(
              "The analytics refresh exhausted its bounded retries. Your prior report was not replaced.",
            );
          }
        })
        .catch((error: unknown) => {
          if (controller.signal.aborted || isAbortError(error)) return;
          setFailure(
            requestErrorMessage(
              error,
              pollFailureCount >= 4
                ? "Automatic refresh checks paused after repeated connection failures. Reload the authoritative report to continue."
                : "The analytics refresh status could not be checked. Another bounded check will follow.",
            ),
          );
          setPollFailureCount((current) => Math.min(current + 1, 5));
        });
    }, delay);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [appliedFilters, load, pollFailureCount, refresh]);

  useEffect(
    () => () => {
      pollingController.current?.abort();
      refreshController.current?.abort();
    },
    [],
  );

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = { ...filters };
    const signature = analyticsFilterSignature(next);
    filterEpoch.current += 1;
    appliedSignature.current = signature;
    pollingController.current?.abort();
    refreshController.current?.abort();
    refreshController.current = undefined;
    refreshInFlight.current = undefined;
    if (refreshIntent.current?.signature !== signature) {
      refreshIntent.current = undefined;
    }
    setSuccess(undefined);
    setFailure(undefined);
    setReport(undefined);
    setRefresh(undefined);
    setRefreshing(false);
    setPollFailureCount(0);
    setAppliedFilters(next);
  }

  async function startRefresh() {
    const signature = analyticsFilterSignature(appliedFilters);
    if (
      refreshInFlight.current === signature ||
      appliedSignature.current !== signature
    ) {
      return;
    }
    if (
      !refreshIntent.current ||
      refreshIntent.current.signature !== signature
    ) {
      refreshIntent.current = {
        key: intentKey(appliedFilters),
        signature,
      };
    }
    const epoch = filterEpoch.current;
    const controller = new AbortController();
    refreshController.current?.abort();
    refreshController.current = controller;
    refreshInFlight.current = signature;
    setRefreshing(true);
    setPollFailureCount(0);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const requestKey = refreshIntent.current.key;
      const next = await requestAnalyticsRefresh(
        appliedFilters,
        requestKey,
        controller.signal,
      );
      if (
        controller.signal.aborted ||
        epoch !== filterEpoch.current ||
        appliedSignature.current !== signature ||
        !refreshMatchesFilters(next, appliedFilters)
      ) {
        return;
      }
      if (refreshIntent.current?.key === requestKey) {
        refreshIntent.current = undefined;
      }
      setRefresh(next);
      setSuccess(
        "Analytics refresh queued. This page will update automatically.",
      );
    } catch (error) {
      if (
        controller.signal.aborted ||
        epoch !== filterEpoch.current ||
        isAbortError(error)
      ) {
        return;
      }
      setFailure(
        requestErrorMessage(
          error,
          "The analytics refresh could not be queued.",
        ),
      );
    } finally {
      if (refreshInFlight.current === signature) {
        refreshInFlight.current = undefined;
        setRefreshing(false);
      }
      if (refreshController.current === controller) {
        refreshController.current = undefined;
      }
    }
  }

  const scopeDescription =
    scopes.find((scope) => scope.value === appliedFilters.scope)?.description ??
    "";
  const refreshActive =
    refresh?.status === "queued" ||
    refresh?.status === "running" ||
    refresh?.status === "retry_wait";

  return (
    <main
      className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8"
      id="main-content"
    >
      <PageHeader
        description="Purpose-limited snapshots summarize your own workspace. Complete source watermarks and visible small-cohort suppression keep every report auditable."
        eyebrow="Long-term growth"
        title="Career Analytics"
      />

      <Alert title="Interpretation boundary" tone="info">
        <div className="flex items-start gap-3">
          <ShieldCheck aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
          <p data-testid="non-causal-interpretation">
            {NON_CAUSAL_INTERPRETATION}
          </p>
        </div>
      </Alert>

      <Card className="p-5">
        <form
          className="grid gap-4 md:grid-cols-[minmax(12rem,1fr)_minmax(10rem,1fr)_minmax(10rem,1fr)_auto]"
          onSubmit={applyFilters}
        >
          <label className="grid gap-1.5 text-sm font-bold">
            View
            <Select
              onChange={(event) =>
                setFilters((current) => ({
                  ...current,
                  scope: event.target.value as AnalyticsScope,
                }))
              }
              value={filters.scope}
            >
              {scopes.map((scope) => (
                <option key={scope.value} value={scope.value}>
                  {scope.label}
                </option>
              ))}
            </Select>
          </label>
          <label className="grid gap-1.5 text-sm font-bold">
            Window start
            <Input
              max={filters.windowEnd}
              onChange={(event) =>
                setFilters((current) => ({
                  ...current,
                  windowStart: event.target.value,
                }))
              }
              required
              type="date"
              value={filters.windowStart}
            />
          </label>
          <label className="grid gap-1.5 text-sm font-bold">
            Window end
            <Input
              min={filters.windowStart}
              onChange={(event) =>
                setFilters((current) => ({
                  ...current,
                  windowEnd: event.target.value,
                }))
              }
              required
              type="date"
              value={filters.windowEnd}
            />
          </label>
          <Button className="md:self-end" type="submit" variant="secondary">
            Apply window
          </Button>
        </form>
      </Card>

      {success && (
        <Alert title="Refresh status" tone="success">
          <p role="status">{success}</p>
        </Alert>
      )}
      {failure && report && (
        <Alert title="Analytics update failed" tone="danger">
          <p>{failure}</p>
          <Button
            className="mt-3"
            onClick={() => void load(appliedFilters)}
            variant="secondary"
          >
            Reload authoritative report
          </Button>
        </Alert>
      )}
      {refresh && <RefreshStatus refresh={refresh} />}

      {loading && !report ? (
        <AnalyticsLoading embedded />
      ) : failure && !report ? (
        <ErrorState
          description={failure}
          onRetry={() => void load(appliedFilters)}
          title="Career Analytics unavailable"
        />
      ) : report ? (
        <>
          <Card className="p-5 sm:p-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-2xl font-black">
                    {humanize(report.scope)} report
                  </h2>
                  <Badge tone={freshnessTone(report.freshness)}>
                    {humanize(report.freshness)}
                  </Badge>
                </div>
                <p className="mt-2 text-sm text-muted">{scopeDescription}</p>
                <p className="mt-1 text-sm text-muted">
                  {formattedDate(report.windowStart)} –{" "}
                  {formattedDate(report.windowEnd)} · Generated{" "}
                  {formattedDateTime(report.generatedAt)}
                </p>
                <p className="mt-1 text-sm text-muted">
                  Calendar timezone: {report.timezone}
                </p>
                <p className="mt-2 text-xs text-muted">
                  Metric definition {report.metricDefinitionVersion}
                </p>
              </div>
              <Button
                disabled={refreshActive}
                loading={refreshing}
                loadingLabel="Queueing refresh…"
                onClick={() => void startRefresh()}
              >
                <RefreshCcw aria-hidden="true" className="size-4" />
                Refresh report
              </Button>
            </div>
            {report.freshness === "stale" && (
              <Alert className="mt-5" title="Stale snapshot" tone="warning">
                <p>
                  Source data changed after this snapshot. Refresh before using
                  it for planning.
                </p>
              </Alert>
            )}
            <div className="mt-5 rounded-xl bg-surface-subtle p-4 text-sm leading-6">
              <strong>Recorded interpretation:</strong>{" "}
              {report.payload?.interpretation ?? report.interpretation}
              <p className="mt-2 font-semibold text-muted">
                {NON_CAUSAL_INTERPRETATION}
              </p>
            </div>
            <div className="mt-5 grid gap-3">
              <MetricSemantics report={report} />
              <Watermarks report={report} />
            </div>
          </Card>

          <ReportContent report={report} />
        </>
      ) : null}

      <aside className="rounded-2xl border border-line bg-surface-subtle p-5 text-sm leading-6 text-muted">
        <div className="flex items-start gap-3">
          <Clock3 aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
          <p>
            Refresh jobs are bounded, idempotent, and owner-scoped. A failed or
            changing source snapshot never replaces the last complete report.
            This page does not expose resume text, evidence statements, contact
            details, or application notes.
          </p>
        </div>
      </aside>
    </main>
  );
}

export function AnalyticsLoading({ embedded = false }: { embedded?: boolean }) {
  const content = <LoadingSkeleton />;
  if (embedded) return content;
  return (
    <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
      {content}
    </main>
  );
}

export function AnalyticsRouteError({ reset }: { reset: () => void }) {
  return (
    <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
      <ErrorState
        description="The Career Analytics route could not be rendered. No source data or stored report was changed."
        onRetry={reset}
        title="Career Analytics unavailable"
      />
    </main>
  );
}
