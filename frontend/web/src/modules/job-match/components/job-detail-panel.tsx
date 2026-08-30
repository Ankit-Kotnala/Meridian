"use client";

import {
  ArrowUpCircle,
  Bookmark,
  BookmarkCheck,
  CheckCircle2,
  ExternalLink,
  Target,
  TriangleAlert,
  X,
} from "lucide-react";
import type { ComponentType } from "react";

import { Badge, Button, Card, cn } from "@rezumi/ui";

import type { JobMatchAnalysis, OpportunityPriority } from "../api/types";

import { requirementCoverage, type JobSelection } from "./job-selection";

type MetricTone = "success" | "warning" | "primary" | "muted";

type ReadinessMetric = {
  icon: ComponentType<{ className?: string }>;
  id: string;
  label: string;
  status: string;
  tone: MetricTone;
  value: number;
};

const metricTones: Record<MetricTone, { bar: string; icon: string }> = {
  success: { bar: "bg-success", icon: "text-success-strong" },
  warning: { bar: "bg-warning-visual", icon: "text-warning-strong" },
  primary: { bar: "bg-primary", icon: "text-primary" },
  muted: { bar: "bg-line-strong", icon: "text-muted" },
};

const readinessLabels: Record<string, string> = {
  insufficient_data: "Needs evidence",
  needs_work: "Needs work",
  strong: "Ready",
  viable: "Viable",
};

/** Right column of the job search: everything known about one opportunity. */
export function JobDetailPanel({
  analysis,
  analyzing,
  applying,
  onAnalyze,
  onApply,
  onClose,
  onOpenMatrix,
  onSave,
  priority,
  saving,
  selection,
}: {
  analysis: JobMatchAnalysis | undefined;
  analyzing: boolean;
  applying: boolean;
  onAnalyze: () => void;
  onApply: () => void;
  onClose: () => void;
  onOpenMatrix: () => void;
  onSave: () => void;
  priority: OpportunityPriority | undefined;
  saving: boolean;
  selection: JobSelection;
}) {
  const { job } = selection;
  const saved = job !== undefined;
  const metrics = readinessMetrics(selection, analysis, priority);

  return (
    <Card as="aside" aria-labelledby="job-detail-heading">
      <div className="p-5">
        <div className="flex items-start justify-between gap-3">
          <h2
            className="text-base font-semibold leading-6 tracking-[-0.01em] text-foreground"
            id="job-detail-heading"
          >
            {selection.title}
          </h2>
          <div className="flex shrink-0 items-center gap-1">
            <button
              aria-label={saved ? "Saved to my jobs" : "Save to my jobs"}
              className="rounded-[var(--radius-control)] p-1.5 text-muted-strong hover:bg-surface-subtle hover:text-foreground disabled:opacity-60"
              disabled={saved || saving}
              onClick={onSave}
              type="button"
            >
              {saved ? (
                <BookmarkCheck aria-hidden="true" className="size-4" />
              ) : (
                <Bookmark aria-hidden="true" className="size-4" />
              )}
            </button>
            <button
              aria-label="Close job details"
              className="rounded-[var(--radius-control)] p-1.5 text-muted-strong hover:bg-surface-subtle hover:text-foreground"
              onClick={onClose}
              type="button"
            >
              <X aria-hidden="true" className="size-4" />
            </button>
          </div>
        </div>

        <p className="mt-1 text-xs text-muted">
          {[selection.company, selection.location]
            .filter(Boolean)
            .join(" / ") || "Location not stated"}
        </p>

        <div className="mt-3 flex flex-wrap gap-2">
          {selection.platform && (
            <Badge tone="neutral">{selection.platform}</Badge>
          )}
          {selection.remote && <Badge tone="success">Remote</Badge>}
          {job && (
            <Badge tone="neutral">
              {job.requirements.length} requirement
              {job.requirements.length === 1 ? "" : "s"}
            </Badge>
          )}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button
            className="flex-1 whitespace-nowrap px-3"
            loading={analyzing}
            onClick={onAnalyze}
            variant="secondary"
          >
            <Target aria-hidden="true" className="size-4" />
            Analyze
          </Button>
          <Button
            className="flex-1 whitespace-nowrap px-3"
            loading={applying}
            onClick={onApply}
          >
            <Target aria-hidden="true" className="size-4" />
            Apply for me
          </Button>
          {selection.applicationUrl && (
            <a
              aria-label={`Open ${selection.title} on the source job board`}
              className="inline-flex min-h-10 items-center justify-center rounded-[var(--radius-pill)] border border-line-strong bg-surface px-3.5 text-foreground hover:border-primary/35 hover:bg-primary-soft/60"
              href={selection.applicationUrl}
              rel="noreferrer noopener"
              target="_blank"
            >
              <ExternalLink aria-hidden="true" className="size-4" />
            </a>
          )}
        </div>
      </div>

      <div className="border-t border-line px-5 py-4">
        <h3 className="text-sm font-semibold text-foreground">
          Application readiness
        </h3>
        <ul className="mt-3 space-y-3">
          {metrics.map((metric) => {
            const tone = metricTones[metric.tone];
            const Icon = metric.icon;
            return (
              <li className="flex items-center gap-3" key={metric.id}>
                <Icon aria-hidden="true" className={cn("size-5", tone.icon)} />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-semibold text-foreground">
                    {metric.label}
                  </p>
                  <p className="text-xs text-muted">{metric.status}</p>
                </div>
                <div
                  aria-label={`${metric.label}: ${metric.status}`}
                  aria-valuemax={100}
                  aria-valuemin={0}
                  aria-valuenow={metric.value}
                  className="h-1.5 w-32 shrink-0 overflow-hidden rounded-full bg-surface-inset"
                  role="progressbar"
                >
                  <div
                    className={cn("h-full rounded-full", tone.bar)}
                    style={{ width: `${metric.value}%` }}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="grid gap-5 border-t border-line px-5 py-4 sm:grid-cols-2 sm:gap-0">
        <div className="sm:pr-5">
          <h3 className="text-sm font-semibold text-foreground">
            Requirement matrix
          </h3>
          {analysis ? (
            <>
              <Badge className="mt-2" tone="primary">
                {readinessLabels[analysis.readinessLabel] ??
                  analysis.readinessLabel}
              </Badge>
              <p className="mt-2 line-clamp-3 text-xs leading-5 text-muted">
                {analysis.summary}
              </p>
            </>
          ) : (
            <>
              <Badge className="mt-2" tone="primary">
                Helpful
              </Badge>
              <p className="mt-2 line-clamp-3 text-xs leading-5 text-muted">
                {selection.sourceText?.trim() ||
                  "Analyze this job to map its explicit requirements to eligible career evidence."}
              </p>
            </>
          )}
          <button
            className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:text-primary-strong"
            onClick={onOpenMatrix}
            type="button"
          >
            View more
            <ExternalLink aria-hidden="true" className="size-3.5" />
          </button>
        </div>
        <div className="border-t border-line pt-4 sm:border-l sm:border-t-0 sm:pl-5 sm:pt-0">
          <h3 className="text-sm font-semibold text-foreground">
            Opportunity priority
          </h3>
          {priority ? (
            <>
              <p className="mt-2 text-xs font-semibold text-foreground">
                {Math.round(priority.priorityScoreBasisPoints / 100)}/100
              </p>
              <p className="mt-1 line-clamp-4 text-xs leading-5 text-muted">
                {priority.nextAction}
              </p>
            </>
          ) : (
            <p className="mt-2 text-xs leading-5 text-muted">
              Analyze a saved job before calculating opportunity priority.
            </p>
          )}
        </div>
      </div>
    </Card>
  );
}

function readinessMetrics(
  selection: JobSelection,
  analysis: JobMatchAnalysis | undefined,
  priority: OpportunityPriority | undefined,
): ReadinessMetric[] {
  const { job } = selection;
  const coverage = analysis ? requirementCoverage(analysis) : undefined;

  const evidence: ReadinessMetric = !job
    ? {
        icon: Bookmark,
        id: "evidence",
        label: "Evidence match",
        status: "Save this job first",
        tone: "muted",
        value: 0,
      }
    : !analysis
      ? {
          icon: ArrowUpCircle,
          id: "evidence",
          label: "Evidence match",
          status: "Not analyzed",
          tone: "primary",
          value: 0,
        }
      : analysis.displayScore === null
        ? {
            icon: TriangleAlert,
            id: "evidence",
            label: "Evidence match",
            status: "Needs evidence",
            tone: "warning",
            value: 0,
          }
        : {
            icon: analysis.displayScore >= 70 ? CheckCircle2 : TriangleAlert,
            id: "evidence",
            label: "Evidence match",
            status:
              readinessLabels[analysis.readinessLabel] ??
              analysis.readinessLabel,
            tone: analysis.displayScore >= 70 ? "success" : "warning",
            value: analysis.displayScore,
          };

  const requirements: ReadinessMetric = !job
    ? {
        icon: Bookmark,
        id: "coverage",
        label: "Requirement coverage",
        status: "Save this job first",
        tone: "muted",
        value: 0,
      }
    : !coverage
      ? {
          icon: ArrowUpCircle,
          id: "coverage",
          label: "Requirement coverage",
          status: `${job.requirements.length} extracted`,
          tone: "primary",
          value: 0,
        }
      : {
          icon: coverage.percent >= 80 ? CheckCircle2 : TriangleAlert,
          id: "coverage",
          label: "Requirement coverage",
          status:
            coverage.percent >= 80
              ? "Full"
              : coverage.percent > 0
                ? "Partial"
                : "None",
          tone: coverage.percent >= 80 ? "success" : "warning",
          value: coverage.percent,
        };

  const opportunity: ReadinessMetric = priority
    ? {
        icon: priority.priorityLabel === "high" ? CheckCircle2 : ArrowUpCircle,
        id: "priority",
        label: "Application priority",
        status:
          priority.priorityLabel.charAt(0).toUpperCase() +
          priority.priorityLabel.slice(1),
        tone: priority.priorityLabel === "high" ? "success" : "primary",
        value: Math.round(priority.priorityScoreBasisPoints / 100),
      }
    : {
        icon: ArrowUpCircle,
        id: "priority",
        label: "Application priority",
        status: analysis ? "Calculate" : "Analyze",
        tone: "warning",
        value: analysis ? 50 : 25,
      };

  return [evidence, requirements, opportunity];
}
