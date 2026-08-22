import {
  AlertTriangle,
  Archive,
  ArrowUpRight,
  BadgeCheck,
  Check,
  ChevronRight,
  CircleDashed,
  Info,
  NotebookPen,
  ShieldCheck,
  Sparkles,
  Target,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";

import { Badge, cn, buttonStyles } from "@rezumi/ui";

import type {
  DashboardAttentionItem,
  DashboardCount,
  DashboardPipeline,
  DashboardPipelineGroup,
  DashboardRecordCounts,
} from "../server/dashboard-summary";

/** Shared tile chrome so the bento grid stays visually consistent. */
function Tile({
  accent = false,
  action,
  children,
  className,
  label,
  labelId,
  title,
}: {
  accent?: boolean;
  action?: { href: string; label: string };
  children: React.ReactNode;
  className?: string;
  label: string;
  labelId: string;
  title?: string;
}) {
  return (
    <section
      aria-labelledby={labelId}
      className={cn("workspace-panel", className)}
    >
      <div className="workspace-panel-header">
        <h2 id={labelId}>{label}</h2>
        {action && (
          <Link className="workspace-panel-link" href={action.href}>
            {action.label}
            <ArrowUpRight aria-hidden="true" className="size-3.5" />
          </Link>
        )}
      </div>
      {title && (
        <p className="px-4 pt-2 text-sm font-semibold text-foreground sm:px-5">
          {title}
        </p>
      )}
      {children}
    </section>
  );
}

function CountValue({ count }: { count: DashboardCount }) {
  if (count.kind === "unavailable") {
    return (
      <span aria-label="Unavailable" className="text-muted">
        &mdash;
      </span>
    );
  }
  return (
    <>
      {count.value}
      {count.atLeast ? "+" : ""}
    </>
  );
}

const RECORD_ROWS: readonly {
  count: keyof DashboardRecordCounts;
  href: string;
  icon: LucideIcon;
  label: string;
}[] = [
  {
    count: "experiences",
    href: "/career-profile",
    icon: UserRound,
    label: "Experiences",
  },
  {
    count: "skills",
    href: "/career-profile",
    icon: Sparkles,
    label: "Skills",
  },
  { count: "evidence", href: "/evidence", icon: Archive, label: "Evidence" },
  {
    count: "achievements",
    href: "/achievement-inbox",
    icon: NotebookPen,
    label: "Open achievements",
  },
];

/**
 * Key figures for the account's own record, as a row of large-numeral cards.
 * Each figure links to the surface that owns it, and an unavailable count is
 * rendered as an explicit dash rather than being collapsed into a zero.
 */
export function CareerRecordStats({
  record,
}: {
  record: DashboardRecordCounts;
}) {
  const unavailable = RECORD_ROWS.some(
    ({ count }) => record[count].kind === "unavailable",
  );

  return (
    <section
      aria-labelledby="career-record-heading"
      className="workspace-panel min-w-0"
    >
      <div className="workspace-panel-header">
        <h2 id="career-record-heading">Your career record</h2>
        <Link className="workspace-panel-link" href="/career-profile">
          Open
          <ArrowUpRight aria-hidden="true" className="size-3.5" />
        </Link>
      </div>

      <ul className="grid grid-cols-2 divide-x divide-y divide-line sm:grid-cols-4 sm:divide-y-0">
        {RECORD_ROWS.map(({ count, href, icon: Icon, label }) => (
          <li className="min-w-0" key={label}>
            <Link className="stat-tile group block h-full" href={href}>
              <span className="stat-tile-icon">
                <Icon aria-hidden="true" className="size-4" strokeWidth={1.75} />
              </span>
              <span className="stat-tile-label">{label}</span>
              <span className="stat-tile-value">
                <CountValue count={record[count]} />
              </span>
            </Link>
          </li>
        ))}
      </ul>

      {unavailable && (
        <p className="border-t border-line px-4 py-2.5 text-xs leading-5 text-muted sm:px-5">
          Count unavailable right now
        </p>
      )}
    </section>
  );
}

export function ResumeHelpBanner() {
  return (
    <div className="workspace-help-strip">
      <div className="flex items-center gap-2.5 text-sm font-medium text-foreground">
        <Target aria-hidden="true" className="size-4 shrink-0 text-primary" />
        <span>Need help with your resume?</span>
      </div>
      <Link
        className={cn(
          buttonStyles.base,
          buttonStyles.primary,
          "w-full justify-center sm:w-auto sm:shrink-0",
        )}
        href="/resume-health/account"
      >
        Start Resume Review
        <ArrowUpRight aria-hidden="true" className="size-4" />
      </Link>
    </div>
  );
}

const attentionTones: Record<
  DashboardAttentionItem["tone"],
  { className: string; icon: LucideIcon }
> = {
  danger: { className: "bg-danger-soft text-danger", icon: AlertTriangle },
  info: { className: "bg-info-soft text-info-strong", icon: Info },
  warning: {
    className: "bg-warning-soft text-warning-strong",
    icon: AlertTriangle,
  },
};

export function AttentionPanel({
  degraded,
  items,
}: {
  degraded: boolean;
  items: readonly DashboardAttentionItem[];
}) {
  return (
    <Tile
      accent={items.length > 0}
      className="min-w-0"
      label={`Needs your review${items.length > 0 ? ` · ${items.length}` : ""}`}
      labelId="attention-heading"
    >
      {items.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-1.5 px-6 py-10 text-center">
          <span className="grid size-9 place-items-center rounded-full bg-success-soft text-success-strong">
            <Check aria-hidden="true" className="size-4" />
          </span>
          <p className="mt-1 text-sm font-semibold text-foreground">
            {degraded
              ? "No reviewable items could be loaded"
              : "Nothing is waiting on you"}
          </p>
          <p className="max-w-xs text-xs leading-5 text-muted">
            {degraded
              ? "Part of your account state is temporarily unavailable. Nothing was changed."
              : "Items appear here when your record, applications, or reminders need a decision."}
          </p>
        </div>
      ) : (
        <ul className="mt-1 flex-1 divide-y divide-line/70">
          {items.map(({ description, href, id, label, tone }) => {
            const { className, icon: Icon } = attentionTones[tone];
            return (
              <li key={id}>
                <Link
                  className="group flex items-start gap-3 px-4 py-3 transition-colors hover:bg-primary-soft/30 sm:px-5"
                  href={href}
                >
                  <span
                    className={cn(
                      "mt-px grid size-7 shrink-0 place-items-center rounded-[var(--radius-small)]",
                      className,
                    )}
                  >
                    <Icon aria-hidden="true" className="size-3.5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-semibold leading-5 text-foreground">
                      {label}
                    </span>
                    <span className="mt-0.5 block text-xs leading-5 text-muted">
                      {description}
                    </span>
                  </span>
                  <ChevronRight
                    aria-hidden="true"
                    className="mt-1 size-4 shrink-0 text-muted transition-transform group-hover:translate-x-0.5"
                  />
                </Link>
              </li>
            );
          })}
        </ul>
      )}
      {degraded && items.length > 0 && (
        <p className="px-4 pb-4 pt-2 text-xs leading-5 text-muted sm:px-5">
          Part of your account state could not be loaded, so this list may be
          incomplete.
        </p>
      )}
    </Tile>
  );
}

const pipelineTone: Record<DashboardPipelineGroup["key"], string> = {
  applied: "var(--primary)",
  closed: "var(--border-strong)",
  exploring: "var(--info)",
  interviewing: "var(--accent)",
  offer: "var(--success)",
};

function pipelineSummaryText(
  groups: readonly DashboardPipelineGroup[],
  total: number,
  atLeast: boolean,
): string {
  const parts = groups
    .filter(({ count }) => count > 0)
    .map(({ count, label }) => `${label}: ${count}`);
  return `${total}${atLeast ? " or more" : ""} tracked ${total === 1 ? "application" : "applications"}. ${parts.join(", ")}.`;
}

export function PipelinePanel({ pipeline }: { pipeline: DashboardPipeline }) {
  return (
    <Tile
      action={{ href: "/applications", label: "Open" }}
      className="min-w-0"
      label="Application pipeline"
      labelId="pipeline-heading"
    >
      <div className="flex flex-1 flex-col px-4 pb-4 pt-3 sm:px-5 sm:pb-5">
        {pipeline.kind === "unavailable" ? (
          <p className="text-sm leading-6 text-muted">
            Your application pipeline could not be loaded. No application was
            changed.
          </p>
        ) : pipeline.total === 0 ? (
          <div className="flex flex-1 flex-col justify-center gap-2 py-4">
            <p className="text-sm leading-6 text-muted">
              You are not tracking any applications yet.
            </p>
            <Link className="text-link text-sm" href="/job-match">
              Start from a job match
            </Link>
          </div>
        ) : (
          <>
            <div className="flex items-baseline gap-2">
              <span className="metric-value text-4xl text-foreground">
                {pipeline.total}
                {pipeline.atLeast ? "+" : ""}
              </span>
              <span className="text-xs text-muted">
                tracked
                {pipeline.openTasks > 0
                  ? ` · ${pipeline.openTasks} open ${pipeline.openTasks === 1 ? "task" : "tasks"}`
                  : ""}
              </span>
            </div>

            <div
              aria-hidden="true"
              className="mt-3 flex h-2 w-full gap-0.5 overflow-hidden rounded-full bg-surface-inset"
            >
              {pipeline.groups
                .filter(({ count }) => count > 0)
                .map(({ count, key }) => (
                  <span
                    className="h-full first:rounded-l-full last:rounded-r-full"
                    key={key}
                    style={{ background: pipelineTone[key], flexGrow: count }}
                  />
                ))}
            </div>
            <p className="sr-only">
              {pipelineSummaryText(
                pipeline.groups,
                pipeline.total,
                pipeline.atLeast,
              )}
            </p>

            <ul className="mt-3 divide-y divide-line/70 border-t border-line/70">
              {pipeline.groups.map(({ count, key, label }) => (
                <li
                  className="flex items-center justify-between gap-3 py-1.5 text-sm"
                  key={key}
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <span
                      aria-hidden="true"
                      className="size-2 shrink-0 rounded-full"
                      style={{ background: pipelineTone[key] }}
                    />
                    <span className="truncate text-xs text-muted-strong">
                      {label}
                    </span>
                  </span>
                  <span className="text-sm font-semibold tabular-nums text-foreground">
                    {count}
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </Tile>
  );
}

const STANDING_STEPS: readonly string[] = [
  "Email confirmed",
  "Career record",
  "Evidence confirmed",
];

/**
 * Corp ID standing on the home screen. Standing is derived from the same checks
 * as the Settings credential, so the two can never disagree.
 */
export function StandingTile({
  corpId,
  record,
}: {
  corpId: string | null;
  record: DashboardRecordCounts;
}) {
  if (!corpId) return null;
  const met = (count: DashboardCount) =>
    count.kind === "count" && count.value > 0;
  const reached = [
    true,
    met(record.experiences),
    met(record.evidenceConfirmed),
  ];
  const label = reached[2]
    ? "Evidenced"
    : reached[1]
      ? "Profiled"
      : "Registered";

  return (
    <Tile
      action={{ href: "/settings", label: "Card" }}
      className="min-w-0"
      label="Rezumi Corp ID"
      labelId="standing-heading"
    >
      <div className="flex flex-1 flex-col px-4 pb-4 pt-3 sm:px-5 sm:pb-5">
        <p className="font-mono text-lg font-bold tracking-[0.06em] text-foreground">
          {corpId}
        </p>
        <Badge className="mt-2 self-start" tone="primary">
          <BadgeCheck aria-hidden="true" className="size-3.5" />
          {label}
        </Badge>

        <ul className="mt-4 space-y-1.5">
          {STANDING_STEPS.map((step, index) => (
            <li className="flex items-center gap-2 text-xs" key={step}>
              <span
                className={cn(
                  "grid size-4 shrink-0 place-items-center rounded-full",
                  reached[index]
                    ? "bg-success-soft text-success-strong"
                    : "bg-surface-inset text-muted",
                )}
              >
                {reached[index] ? (
                  <Check aria-hidden="true" className="size-2.5" />
                ) : (
                  <CircleDashed aria-hidden="true" className="size-2.5" />
                )}
              </span>
              <span
                className={reached[index] ? "text-muted-strong" : "text-muted"}
              >
                {step}
              </span>
              <span className="sr-only">
                {reached[index] ? "complete" : "not yet complete"}
              </span>
            </li>
          ))}
        </ul>

        <p className="mt-auto pt-4 text-[0.6875rem] leading-4 text-muted">
          Records your standing with Rezumi. Not an employer or third-party
          verification.
        </p>
      </div>
    </Tile>
  );
}

export function TruthLockNote() {
  return (
    <footer className="flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-line pt-4 text-xs leading-5 text-muted">
      <ShieldCheck aria-hidden="true" className="size-3.5 shrink-0" />
      <span>
        One career record upstream; resumes, answers, and stories are derived
        from it. Every measurement here is an internal, explainable
        signal&mdash;never an employer or applicant-tracking-system score.
      </span>
      <Link className="text-link" href="/methodology">
        Scoring methodology
      </Link>
    </footer>
  );
}
