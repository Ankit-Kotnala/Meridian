import {
  Archive,
  ArrowUpRight,
  BadgeCheck,
  Briefcase,
  Check,
  ChevronRight,
  CircleDashed,
  FileText,
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
  DashboardApplicationRow,
  DashboardAttentionItem,
  DashboardCount,
  DashboardGrowth,
  DashboardJobHunt,
  DashboardPipeline,
  DashboardPipelineGroup,
  DashboardPrepare,
  DashboardRecordCounts,
} from "../server/dashboard-summary";
import { recordStatsFootnote } from "../lib/dashboard-user-copy";

/** Shared tile chrome so the bento grid stays visually consistent. */
function Tile({
  action,
  children,
  className,
  label,
  labelId,
  title,
}: {
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
  hint: string;
  href: string;
  icon: LucideIcon;
  label: string;
}[] = [
  {
    count: "experiences",
    hint: "Roles & jobs",
    href: "/career-profile",
    icon: UserRound,
    label: "Roles",
  },
  {
    count: "skills",
    hint: "Strengths listed",
    href: "/career-profile",
    icon: Sparkles,
    label: "Skills",
  },
  {
    count: "evidence",
    hint: "Proof on file",
    href: "/evidence",
    icon: Archive,
    label: "Evidence",
  },
  {
    count: "achievements",
    hint: "Drafts & ready",
    href: "/achievement-inbox",
    icon: NotebookPen,
    label: "Achievements",
  },
];

function CountCardValue({ count }: { count: DashboardCount }) {
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

/**
 * The four headline cards across the top of Home: application activity and
 * profile record counts at a glance. Every value is read from the account's
 * own data — a metric renders as "—" rather than a guessed number when its
 * source is unavailable.
 */
export function HomeStatCards({
  pipeline,
  record,
  resumes,
}: {
  pipeline: DashboardPipeline;
  record: DashboardRecordCounts;
  resumes: DashboardCount;
}) {
  return (
    <ul
      aria-label="Home overview"
      className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4"
    >
      <li className="min-w-0">
        <div className="stat-card-tile">
          <div className="flex items-start justify-between gap-2">
            <span className="text-[0.8125rem] font-semibold text-foreground">
              Active applications
            </span>
            <span className="stat-card-tile-icon">
              <Briefcase
                aria-hidden="true"
                className="size-4"
                strokeWidth={1.75}
              />
            </span>
          </div>
          <span className="stat-card-tile-value">
            {pipeline.kind === "ready" ? (
              <>
                {pipeline.total}
                {pipeline.atLeast ? "+" : ""}
              </>
            ) : (
              <span aria-label="Unavailable" className="text-muted">
                &mdash;
              </span>
            )}
          </span>
          <p className="text-[0.6875rem] text-muted">
            {pipeline.kind === "ready" && pipeline.openTasks > 0
              ? `${pipeline.openTasks} open ${pipeline.openTasks === 1 ? "task" : "tasks"}`
              : "Tracked in your pipeline"}
          </p>
          <Link className="stat-card-tile-link mt-auto" href="/applications">
            View all
            <ArrowUpRight aria-hidden="true" className="size-3" />
          </Link>
        </div>
      </li>

      <li className="min-w-0">
        <div className="stat-card-tile">
          <div className="flex items-start justify-between gap-2">
            <span className="text-[0.8125rem] font-semibold text-foreground">
              Roles
            </span>
            <span className="stat-card-tile-icon">
              <UserRound
                aria-hidden="true"
                className="size-4"
                strokeWidth={1.75}
              />
            </span>
          </div>
          <span className="stat-card-tile-value">
            <CountCardValue count={record.experiences} />
          </span>
          <p className="text-[0.6875rem] text-muted">Roles &amp; jobs</p>
          <Link className="stat-card-tile-link mt-auto" href="/career-profile">
            View all
            <ArrowUpRight aria-hidden="true" className="size-3" />
          </Link>
        </div>
      </li>

      <li className="min-w-0">
        <div className="stat-card-tile">
          <div className="flex items-start justify-between gap-2">
            <span className="text-[0.8125rem] font-semibold text-foreground">
              Skills
            </span>
            <span className="stat-card-tile-icon">
              <Sparkles
                aria-hidden="true"
                className="size-4"
                strokeWidth={1.75}
              />
            </span>
          </div>
          <span className="stat-card-tile-value">
            <CountCardValue count={record.skills} />
          </span>
          <p className="text-[0.6875rem] text-muted">Strengths listed</p>
          <Link className="stat-card-tile-link mt-auto" href="/career-profile">
            Manage
            <ArrowUpRight aria-hidden="true" className="size-3" />
          </Link>
        </div>
      </li>

      <li className="min-w-0">
        <div className="stat-card-tile">
          <div className="flex items-start justify-between gap-2">
            <span className="text-[0.8125rem] font-semibold text-foreground">
              Resumes
            </span>
            <span className="stat-card-tile-icon">
              <FileText
                aria-hidden="true"
                className="size-4"
                strokeWidth={1.75}
              />
            </span>
          </div>
          <span className="stat-card-tile-value">
            <CountCardValue count={resumes} />
          </span>
          <p className="text-[0.6875rem] text-muted">On file</p>
          <Link
            className="stat-card-tile-link mt-auto"
            href="/resume-health/account"
          >
            Manage resumes
            <ArrowUpRight aria-hidden="true" className="size-3" />
          </Link>
        </div>
      </li>
    </ul>
  );
}

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
  const footnote = recordStatsFootnote(record);

  return (
    <section aria-labelledby="career-record-heading" className="min-w-0">
      <h2 className="sr-only" id="career-record-heading">
        Your profile at a glance
      </h2>
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {RECORD_ROWS.map(({ count, hint, href, icon: Icon, label }) => (
          <li className="min-w-0" key={label}>
            <div className="stat-card-tile">
              <div className="flex items-start justify-between gap-2">
                <span className="text-[0.8125rem] font-semibold text-foreground">
                  {label}
                </span>
                <span className="stat-card-tile-icon">
                  <Icon
                    aria-hidden="true"
                    className="size-4"
                    strokeWidth={1.75}
                  />
                </span>
              </div>
              <span className="stat-card-tile-value">
                <CountValue count={record[count]} />
              </span>
              <p className="text-[0.6875rem] text-muted">{hint}</p>
              <Link className="stat-card-tile-link mt-auto" href={href}>
                {label === "Roles" ? "View all" : "Manage"}
                <ArrowUpRight aria-hidden="true" className="size-3" />
              </Link>
            </div>
          </li>
        ))}
      </ul>

      {unavailable ? (
        <p className="mt-2 px-1 text-xs leading-5 text-muted">
          Some counts could not be loaded — try refreshing.
        </p>
      ) : (
        footnote && (
          <p className="mt-2 px-1 text-xs leading-5 text-muted">{footnote}</p>
        )
      )}
    </section>
  );
}

export function ResumeHelpBanner() {
  return (
    <div className="workspace-help-strip">
      <div className="flex items-center gap-2.5 text-sm font-medium text-foreground">
        <Target aria-hidden="true" className="size-4 shrink-0 text-primary" />
        <span>Want feedback on your resume before you apply?</span>
      </div>
      <Link
        className={cn(
          buttonStyles.base,
          buttonStyles.primary,
          "w-full justify-center sm:w-auto sm:shrink-0",
        )}
        href="/resume-health/account"
      >
        Get resume feedback
        <ArrowUpRight aria-hidden="true" className="size-4" />
      </Link>
    </div>
  );
}

const priorityByTone: Record<
  DashboardAttentionItem["tone"],
  { className: string; label: string }
> = {
  danger: { className: "bg-danger", label: "High" },
  info: { className: "bg-info", label: "Normal" },
  warning: { className: "bg-warning-visual", label: "Medium" },
};

/** "Work queue" — items waiting on the person, rendered as a scannable table. */
export function AttentionPanel({
  degraded,
  items,
}: {
  degraded: boolean;
  items: readonly DashboardAttentionItem[];
}) {
  return (
    <Tile
      className="min-w-0"
      label="Work queue"
      labelId="attention-heading"
      {...(items.length > 0
        ? { action: { href: "/applications", label: "Manage" } }
        : {})}
    >
      {items.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-1.5 px-6 py-10 text-center">
          <span className="grid size-9 place-items-center rounded-full bg-success-soft text-success-strong">
            <Check aria-hidden="true" className="size-4" />
          </span>
          <p className="mt-1 text-sm font-semibold text-foreground">
            {degraded
              ? "Could not load your to-do list"
              : "You're all caught up"}
          </p>
          <p className="max-w-xs text-xs leading-5 text-muted">
            {degraded
              ? "Part of your account could not be reached. Nothing was changed on your end."
              : "Deadlines, drafts, and items waiting on you will show up here."}
          </p>
        </div>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Item</th>
                <th>Area</th>
                <th>Priority</th>
                <th>Due</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {items.map(({ action, area, due, href, id, label, tone }) => {
                const priority = priorityByTone[tone];
                return (
                  <tr key={id}>
                    <td className="text-sm font-semibold text-foreground">
                      {label}
                    </td>
                    <td className="text-sm text-muted-strong">{area}</td>
                    <td>
                      <span className="inline-flex items-center gap-1.5 text-sm text-muted-strong">
                        <span
                          aria-hidden="true"
                          className={cn(
                            "size-2 rounded-full",
                            priority.className,
                          )}
                        />
                        {priority.label}
                      </span>
                    </td>
                    <td className="text-sm text-muted-strong">{due}</td>
                    <td>
                      <Link
                        className={cn(
                          buttonStyles.base,
                          buttonStyles.outline,
                          "!min-h-8 !px-3 !text-xs",
                        )}
                        href={href}
                      >
                        {action}
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
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

const stageDotTone: Record<string, string> = {
  applied: "var(--info)",
  assessment: "var(--accent)",
  interview: "var(--accent)",
  offer: "var(--success)",
  preparing: "var(--muted)",
  ready_to_apply: "var(--muted)",
  recruiter_screen: "var(--accent)",
  rejected: "var(--border-strong)",
  researching: "var(--muted)",
  saved: "var(--muted)",
  withdrawn: "var(--border-strong)",
};

export function PipelinePanel({
  applications,
  pipeline,
}: {
  applications: readonly DashboardApplicationRow[];
  pipeline: DashboardPipeline;
}) {
  return (
    <Tile
      action={{ href: "/applications", label: "View all" }}
      className="min-w-0"
      label="Application pipeline"
      labelId="pipeline-heading"
    >
      <div className="flex flex-1 flex-col">
        {pipeline.kind === "unavailable" ? (
          <p className="px-4 py-4 text-sm leading-6 text-muted sm:px-5">
            Your application pipeline could not be loaded. No application was
            changed.
          </p>
        ) : pipeline.total === 0 ? (
          <div className="flex flex-1 flex-col justify-center gap-2 px-4 py-6 sm:px-5">
            <p className="text-sm leading-6 text-muted">
              You are not tracking any applications yet.
            </p>
            <Link className="text-link text-sm" href="/job-match">
              Start from a job match
            </Link>
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-x-1 gap-y-3 border-b border-line px-4 py-4 sm:px-5">
              {pipeline.groups
                .filter(({ key }) => key !== "closed")
                .map(({ count, key, label }, index) => (
                  <div className="flex items-center" key={key}>
                    {index > 0 && (
                      <ChevronRight
                        aria-hidden="true"
                        className="mx-3 size-4 shrink-0 text-line-strong"
                      />
                    )}
                    <div className="min-w-[4.5rem]">
                      <p className="flex items-center gap-1.5 text-xs font-semibold text-muted-strong">
                        <span
                          aria-hidden="true"
                          className="size-2 rounded-full"
                          style={{ background: pipelineTone[key] }}
                        />
                        {label}
                      </p>
                      <p className="metric-value mt-1 text-2xl text-foreground">
                        {count}
                      </p>
                    </div>
                  </div>
                ))}
              <p className="sr-only">
                {pipelineSummaryText(
                  pipeline.groups,
                  pipeline.total,
                  pipeline.atLeast,
                )}
              </p>
              {pipeline.openTasks > 0 && (
                <p className="ml-auto self-center text-xs text-muted">
                  {pipeline.openTasks} open{" "}
                  {pipeline.openTasks === 1 ? "task" : "tasks"}
                </p>
              )}
            </div>

            {applications.length === 0 ? (
              <p className="px-4 py-4 text-sm leading-6 text-muted sm:px-5">
                Application details could not be loaded.
              </p>
            ) : (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Role</th>
                      <th>Company</th>
                      <th>Stage</th>
                      <th>Applied</th>
                      <th>Next step</th>
                    </tr>
                  </thead>
                  <tbody>
                    {applications.map((row) => (
                      <tr key={row.id}>
                        <td className="text-sm font-semibold text-foreground">
                          {row.jobTitle}
                        </td>
                        <td className="text-sm text-muted-strong">
                          {row.company ?? "—"}
                        </td>
                        <td>
                          <span className="inline-flex items-center gap-1.5 text-sm text-muted-strong">
                            <span
                              aria-hidden="true"
                              className="size-2 rounded-full"
                              style={{
                                background:
                                  stageDotTone[row.stage] ?? "var(--muted)",
                              }}
                            />
                            {row.stageLabel}
                          </span>
                        </td>
                        <td className="text-sm text-muted-strong">
                          {row.appliedAt}
                        </td>
                        <td className="text-sm text-muted-strong">
                          {row.nextStep}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </Tile>
  );
}

export function JobHuntPanel({ jobHunt }: { jobHunt: DashboardJobHunt }) {
  return (
    <Tile
      action={{ href: "/job-match", label: "Open" }}
      className="min-w-0"
      label="Job search"
      labelId="job-hunt-heading"
    >
      <div className="flex flex-1 flex-col px-4 pb-4 pt-3 sm:px-5 sm:pb-5">
        {jobHunt.kind === "unavailable" ? (
          <p className="text-sm leading-6 text-muted">
            Job listings could not be loaded. No preference was changed.
          </p>
        ) : jobHunt.total === 0 ? (
          <p className="text-sm leading-6 text-muted">
            No listings match your target role yet. Set or widen your role
            filter to see suggestions.
          </p>
        ) : (
          <>
            <div className="flex items-baseline gap-2">
              <span className="metric-value text-4xl text-foreground">
                {jobHunt.total}
                {jobHunt.atLeast ? "+" : ""}
              </span>
              <span className="text-xs text-muted">suggested listings</span>
            </div>
            {jobHunt.topTitle && (
              <p className="mt-2 truncate text-sm text-muted-strong">
                Top match: {jobHunt.topTitle}
              </p>
            )}
          </>
        )}
      </div>
    </Tile>
  );
}

export function PreparePanel({ prepare }: { prepare: DashboardPrepare }) {
  return (
    <Tile
      action={{ href: "/interview-prep", label: "Open" }}
      className="min-w-0"
      label="Prepare"
      labelId="prepare-heading"
    >
      <div className="flex flex-1 flex-col px-4 pb-4 pt-3 sm:px-5 sm:pb-5">
        {prepare.kind === "unavailable" ? (
          <p className="text-sm leading-6 text-muted">
            Interview prep and networking status could not be loaded.
          </p>
        ) : prepare.followUpsDue === 0 ? (
          <p className="text-sm leading-6 text-muted">
            No networking follow-ups are due. Interview prep and networking both
            live here.
          </p>
        ) : (
          <div className="flex items-baseline gap-2">
            <span className="metric-value text-4xl text-foreground">
              {prepare.followUpsDue}
            </span>
            <span className="text-xs text-muted">
              networking{" "}
              {prepare.followUpsDue === 1 ? "follow-up" : "follow-ups"} due
            </span>
          </div>
        )}
      </div>
    </Tile>
  );
}

export function GrowthPanel({ growth }: { growth: DashboardGrowth }) {
  return (
    <Tile
      action={{ href: "/career-growth", label: "Open" }}
      className="min-w-0"
      label="Growth"
      labelId="growth-heading"
    >
      <div className="flex flex-1 flex-col px-4 pb-4 pt-3 sm:px-5 sm:pb-5">
        {growth.kind === "unavailable" ? (
          <p className="text-sm leading-6 text-muted">
            Growth tracking could not be loaded.
          </p>
        ) : growth.planned + growth.inProgress === 0 ? (
          <p className="text-sm leading-6 text-muted">
            No development items yet. Confirm a roadmap to start tracking
            growth.
          </p>
        ) : (
          <div className="flex items-baseline gap-2">
            <span className="metric-value text-4xl text-foreground">
              {growth.planned + growth.inProgress}
            </span>
            <span className="text-xs text-muted">
              development items · {growth.inProgress} in progress
            </span>
          </div>
        )}
      </div>
    </Tile>
  );
}

const STANDING_STEPS: readonly string[] = [
  "Email confirmed",
  "Profile started",
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
      label="Your ID"
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
          Your account standing — not an employer or third-party verification.
        </p>
      </div>
    </Tile>
  );
}

function readinessBar({ label, pct }: { label: string; pct: number | null }) {
  const safe = pct === null ? 0 : Math.max(0, Math.min(100, Math.round(pct)));
  const tone =
    safe >= 70 ? "bg-success" : safe >= 40 ? "bg-warning-visual" : "bg-danger";
  return (
    <div key={label}>
      <div className="mb-1.5 flex items-baseline justify-between gap-3 text-sm">
        <span className="font-semibold text-foreground">{label}</span>
        <span className="font-bold tabular-nums text-muted">
          {pct === null ? "—" : `${safe}%`}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-inset">
        <div
          className={cn("h-full rounded-full", tone)}
          style={{ width: `${safe}%` }}
        />
      </div>
    </div>
  );
}

/**
 * Share of the four profile pillars (roles, skills, evidence, achievements)
 * that have at least one entry. Null when a count failed to load, so callers
 * render "—" instead of guessing a percentage.
 */
export function profileCompletenessPercent(
  record: DashboardRecordCounts,
): number | null {
  const filled = [
    record.experiences,
    record.skills,
    record.evidence,
    record.achievements,
  ];
  return filled.every((count) => count.kind === "count")
    ? (filled.filter((count) => count.kind === "count" && count.value > 0)
        .length /
        filled.length) *
        100
    : null;
}

/**
 * Profile readiness — percentages derived only from counts the account
 * already has loaded. A section renders as "—" rather than a guessed number
 * when its inputs are unavailable.
 */
export function ProfileReadinessPanel({
  pipeline,
  record,
}: {
  pipeline: DashboardPipeline;
  record: DashboardRecordCounts;
}) {
  const completeness = profileCompletenessPercent(record);

  const evidenceQuality =
    record.evidence.kind === "count" &&
    record.evidenceConfirmed.kind === "count" &&
    record.evidence.value > 0
      ? (record.evidenceConfirmed.value / record.evidence.value) * 100
      : null;

  const momentum =
    pipeline.kind === "ready" && pipeline.total > 0
      ? (pipeline.groups
          .filter(({ key }) => key !== "exploring" && key !== "closed")
          .reduce((sum, { count }) => sum + count, 0) /
          pipeline.total) *
        100
      : null;

  return (
    <Tile
      className="min-w-0"
      label="Profile readiness"
      labelId="readiness-heading"
    >
      <div className="flex flex-1 flex-col gap-4 px-4 py-4 sm:px-5 sm:py-5">
        {readinessBar({ label: "Profile completeness", pct: completeness })}
        {readinessBar({ label: "Evidence confirmed", pct: evidenceQuality })}
        {readinessBar({ label: "Pipeline momentum", pct: momentum })}
      </div>
    </Tile>
  );
}

export function TruthLockNote() {
  return (
    <footer className="flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-line pt-4 text-xs leading-5 text-muted">
      <ShieldCheck aria-hidden="true" className="size-3.5 shrink-0" />
      <span>
        Your profile is yours — resumes and documents are built from what you
        confirm. Scores are for your planning only, not employer or ATS ratings.
      </span>
      <Link className="text-link" href="/methodology">
        How scoring works
      </Link>
    </footer>
  );
}
