import {
  AlertTriangle,
  Archive,
  ArrowRight,
  BookOpenCheck,
  BriefcaseBusiness,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Info,
  NotebookPen,
  Sparkles,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";

import { Badge, cn, SectionHeader } from "@rezumi/ui";

import type {
  DashboardAttentionItem,
  DashboardCount,
  DashboardPipeline,
  DashboardPipelineGroup,
  DashboardRecordCounts,
} from "../server/dashboard-summary";

/** Renders a count, or an explicit dash when the owning endpoint failed. */
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

function countHint(count: DashboardCount, hint: string): string {
  return count.kind === "unavailable" ? "Count unavailable right now" : hint;
}

function StatTile({
  count,
  hint,
  href,
  icon: Icon,
  label,
}: {
  count: DashboardCount;
  hint: string;
  href: string;
  icon: LucideIcon;
  label: string;
}) {
  return (
    <Link
      className="surface-card surface-interactive group flex flex-col gap-3 rounded-[var(--radius-card)] p-4 sm:p-5"
      href={href}
    >
      <span className="flex items-center justify-between gap-2">
        <span className="grid size-9 place-items-center rounded-[var(--radius-small)] bg-primary-soft text-primary-strong transition-colors group-hover:bg-primary group-hover:text-white">
          <Icon aria-hidden="true" className="size-4" />
        </span>
        <ChevronRight
          aria-hidden="true"
          className="size-4 text-muted transition-transform group-hover:translate-x-0.5"
        />
      </span>
      <span>
        <span className="block font-display text-3xl font-semibold tabular-nums leading-none tracking-[-0.045em] text-foreground">
          <CountValue count={count} />
        </span>
        <span className="mt-2 block text-sm font-semibold text-foreground">
          {label}
        </span>
        <span className="mt-1 block text-xs leading-5 text-muted">
          {countHint(count, hint)}
        </span>
      </span>
    </Link>
  );
}

export function CareerRecordStats({
  record,
}: {
  record: DashboardRecordCounts;
}) {
  return (
    <section aria-labelledby="career-record-heading">
      <SectionHeader
        actions={
          <Link className="text-link text-sm" href="/career-profile">
            Open career profile
          </Link>
        }
        description="Counts come from your own account. Nothing here is estimated or filled in for you."
        id="career-record-heading"
        title="Your career record"
      />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          count={record.experiences}
          hint="Roles and positions on file"
          href="/career-profile"
          icon={UserRound}
          label="Experiences"
        />
        <StatTile
          count={record.skills}
          hint="Skills you can support with evidence"
          href="/career-profile"
          icon={Sparkles}
          label="Skills"
        />
        <StatTile
          count={record.evidence}
          hint="Private records that can ground a claim"
          href="/evidence"
          icon={Archive}
          label="Evidence"
        />
        <StatTile
          count={record.achievements}
          hint="Captured outcomes not yet converted"
          href="/achievement-inbox"
          icon={NotebookPen}
          label="Open achievements"
        />
      </div>
    </section>
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
    <section aria-labelledby="attention-heading" className="flex flex-col">
      <SectionHeader
        description="Derived from your account state. Every item links to the place where you decide."
        id="attention-heading"
        title="Needs your review"
      />
      <div className="data-region flex-1">
        {items.length === 0 ? (
          <div className="flex h-full min-h-44 flex-col items-center justify-center gap-2 p-6 text-center">
            <span className="grid size-10 place-items-center rounded-full bg-success-soft text-success-strong">
              <CheckCircle2 aria-hidden="true" className="size-5" />
            </span>
            <p className="text-sm font-semibold text-foreground">
              {degraded
                ? "No reviewable items could be loaded"
                : "Nothing is waiting on you"}
            </p>
            <p className="max-w-xs text-xs leading-5 text-muted">
              {degraded
                ? "Part of your account state is temporarily unavailable, so this list may be incomplete. Nothing was changed."
                : "New review items appear here when your record, applications, or reminders need a decision."}
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-line">
            {items.map(({ description, href, id, label, tone }) => {
              const { className, icon: Icon } = attentionTones[tone];
              return (
                <li key={id}>
                  <Link
                    className="group flex items-start gap-3 px-4 py-3.5 transition-colors hover:bg-primary-soft/35 sm:px-5"
                    href={href}
                  >
                    <span
                      className={cn(
                        "mt-0.5 grid size-8 shrink-0 place-items-center rounded-[var(--radius-small)]",
                        className,
                      )}
                    >
                      <Icon aria-hidden="true" className="size-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-semibold text-foreground">
                        {label}
                      </span>
                      <span className="mt-1 block text-xs leading-5 text-muted">
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
      </div>
      {degraded && items.length > 0 && (
        <p className="mt-2 text-xs leading-5 text-muted">
          Part of your account state could not be loaded, so this list may be
          incomplete.
        </p>
      )}
    </section>
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
    <section aria-labelledby="pipeline-heading" className="flex flex-col">
      <SectionHeader
        actions={
          <Link className="text-link text-sm" href="/applications">
            Open applications
          </Link>
        }
        description="Stage counts for the opportunities you are tracking."
        id="pipeline-heading"
        title="Application pipeline"
      />
      <div className="data-region flex-1 p-5 sm:p-6">
        {pipeline.kind === "unavailable" ? (
          <p className="text-sm leading-6 text-muted">
            Your application pipeline could not be loaded. No application was
            changed.{" "}
            <Link className="text-link" href="/applications">
              Open Applications
            </Link>{" "}
            to try again.
          </p>
        ) : pipeline.total === 0 ? (
          <div className="flex flex-col items-start gap-3">
            <p className="text-sm leading-6 text-muted">
              You are not tracking any applications yet. Save a role to follow
              it through preparation, submission, and interviews.
            </p>
            <Link className="text-link text-sm" href="/job-match">
              Start from a job match
            </Link>
          </div>
        ) : (
          <>
            <div className="flex items-baseline gap-2">
              <span className="font-display text-3xl font-semibold tabular-nums leading-none tracking-[-0.045em] text-foreground">
                {pipeline.total}
                {pipeline.atLeast ? "+" : ""}
              </span>
              <span className="text-sm text-muted">
                tracked {pipeline.total === 1 ? "application" : "applications"}
                {pipeline.openTasks > 0
                  ? ` · ${pipeline.openTasks} open ${pipeline.openTasks === 1 ? "task" : "tasks"}`
                  : ""}
              </span>
            </div>

            <div
              aria-hidden="true"
              className="mt-4 flex h-2.5 w-full gap-1 overflow-hidden rounded-full bg-surface-inset"
            >
              {pipeline.groups
                .filter(({ count }) => count > 0)
                .map(({ count, key }) => (
                  <span
                    className="h-full rounded-full"
                    key={key}
                    style={{
                      background: pipelineTone[key],
                      flexGrow: count,
                    }}
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

            <ul className="mt-4 divide-y divide-line border-t border-line">
              {pipeline.groups.map(({ count, key, label }) => (
                <li
                  className="flex items-center justify-between gap-3 py-2.5 text-sm"
                  key={key}
                >
                  <span className="flex min-w-0 items-center gap-2.5">
                    <span
                      aria-hidden="true"
                      className="size-2.5 shrink-0 rounded-full"
                      style={{ background: pipelineTone[key] }}
                    />
                    <span className="truncate text-muted-strong">{label}</span>
                  </span>
                  <span className="font-semibold tabular-nums text-foreground">
                    {count}
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </section>
  );
}

const quickLaunch = [
  {
    description: "Roles, skills, and preferences that ground every output.",
    href: "/career-profile",
    icon: UserRound,
    label: "Career Profile",
  },
  {
    description: "Private supporting records behind each factual claim.",
    href: "/evidence",
    icon: Archive,
    label: "Evidence Vault",
  },
  {
    description: "Capture outcomes while the details are still fresh.",
    href: "/achievement-inbox",
    icon: NotebookPen,
    label: "Achievement Inbox",
  },
  {
    description: "Compare a role's requirements against your record.",
    href: "/job-match",
    icon: BriefcaseBusiness,
    label: "Job Match",
  },
  {
    description: "Track stages, tasks, and follow-ups per opportunity.",
    href: "/applications",
    icon: ClipboardList,
    label: "Applications",
  },
  {
    description: "Build grounded stories and rehearse defensible answers.",
    href: "/interview-prep",
    icon: BookOpenCheck,
    label: "Interview Prep",
  },
] as const;

export function QuickLaunch() {
  return (
    <section aria-labelledby="quick-launch-heading">
      <SectionHeader
        description="Jump straight to the workspace you need."
        id="quick-launch-heading"
        title="Go to"
      />
      <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {quickLaunch.map(({ description, href, icon: Icon, label }) => (
          <li key={href}>
            <Link
              className="surface-card surface-interactive group flex h-full items-start gap-3 rounded-[var(--radius-card)] p-4"
              href={href}
            >
              <span className="grid size-9 shrink-0 place-items-center rounded-[var(--radius-small)] bg-surface-subtle text-muted-strong transition-colors group-hover:bg-primary-soft group-hover:text-primary-strong">
                <Icon aria-hidden="true" className="size-4" />
              </span>
              <span className="min-w-0">
                <span className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
                  {label}
                  <ArrowRight
                    aria-hidden="true"
                    className="size-3.5 text-muted opacity-0 transition-opacity group-hover:opacity-100"
                  />
                </span>
                <span className="mt-1 block text-xs leading-5 text-muted">
                  {description}
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function TruthLockNote() {
  return (
    <section
      aria-labelledby="operating-model-heading"
      className="rounded-[var(--radius-card)] border border-line bg-surface-subtle/60 p-5 sm:p-6"
    >
      <Badge tone="primary">How Rezumi works</Badge>
      <h2
        className="mt-3 font-semibold text-foreground"
        id="operating-model-heading"
      >
        One career record, many grounded outputs
      </h2>
      <p className="mt-1.5 max-w-3xl text-sm leading-6 text-muted">
        Rezumi keeps evidence and structured facts upstream. Resumes,
        application answers, interview stories, and networking drafts are
        downstream work products&mdash;not competing sources of truth. Every
        measurement shown in this workspace is an internal, explainable signal,
        never an employer or applicant-tracking-system score.
      </p>
      <Link className="text-link mt-3 inline-flex text-sm" href="/methodology">
        Read the scoring methodology
      </Link>
    </section>
  );
}
