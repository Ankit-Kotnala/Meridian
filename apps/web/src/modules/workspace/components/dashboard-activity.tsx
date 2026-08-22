import {
  CheckCircle2,
  ClipboardList,
  FileHeart,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";

import { cn } from "@rezumi/ui";

import type { DashboardSummary } from "../server/dashboard-summary";
import type { DashboardResumeHealth } from "./dashboard-resume-state";

type ActivityTone = "info" | "primary" | "success" | "warning";

type ActivityItem = {
  description?: string;
  href?: string;
  icon: LucideIcon;
  id: string;
  label: string;
  timeLabel: string;
  tone: ActivityTone;
};

const toneStyles: Record<ActivityTone, string> = {
  info: "bg-info-soft text-info-strong",
  primary: "bg-primary-soft text-primary",
  success: "bg-success-soft text-success-strong",
  warning: "bg-warning-soft text-warning-strong",
};

function resumeActivity(
  resumeHealth: DashboardResumeHealth,
): ActivityItem | undefined {
  if (resumeHealth.kind === "report") {
    return {
      href: `/resume-health/account/report/${encodeURIComponent(resumeHealth.analysisId)}`,
      icon: FileHeart,
      id: "resume-report",
      label: "Resume report generated",
      timeLabel: "Recently",
      tone: "success",
    };
  }
  if (resumeHealth.kind === "review") {
    return {
      href: `/resume-health/account/review/${encodeURIComponent(resumeHealth.documentId)}`,
      icon: FileHeart,
      id: "resume-review",
      label: "Resume ready for field review",
      timeLabel: "Pending",
      tone: "warning",
    };
  }
  if (resumeHealth.kind === "processing") {
    return {
      href: "/resume-health/account",
      icon: FileHeart,
      id: "resume-processing",
      label: "Resume upload processing",
      timeLabel: "In progress",
      tone: "info",
    };
  }
  return undefined;
}

function buildActivityItems(
  resumeHealth: DashboardResumeHealth,
  summary: DashboardSummary,
): ActivityItem[] {
  const items: ActivityItem[] = [];

  const resume = resumeActivity(resumeHealth);
  if (resume) items.push(resume);

  if (summary.pipeline.kind === "ready" && summary.pipeline.total > 0) {
    items.push({
      href: "/applications",
      icon: ClipboardList,
      id: "applications-tracked",
      label: `${summary.pipeline.total}${summary.pipeline.atLeast ? "+" : ""} applications tracked`,
      timeLabel: "Active",
      tone: "info",
    });
  }

  if (
    summary.record.experiences.kind === "count" &&
    summary.record.experiences.value > 0
  ) {
    items.push({
      href: "/career-profile",
      icon: Sparkles,
      id: "career-record",
      label: "Career record updated",
      timeLabel: "Current",
      tone: "primary",
    });
  }

  return items.slice(0, 8);
}

function ActivityRow({ item }: { item: ActivityItem }) {
  const Icon = item.icon;
  const content = (
    <>
      <span className={cn("activity-icon", toneStyles[item.tone])}>
        <Icon aria-hidden="true" className="size-4" strokeWidth={1.75} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold leading-5 text-foreground">
          {item.label}
        </span>
        {item.description && (
          <span className="mt-0.5 block text-xs leading-5 text-muted">
            {item.description}
          </span>
        )}
      </span>
      <span className="shrink-0 text-xs font-medium tabular-nums text-muted">
        {item.timeLabel}
      </span>
    </>
  );

  if (item.href) {
    return (
      <li>
        <Link className="activity-row" href={item.href}>
          {content}
        </Link>
      </li>
    );
  }

  return <li className="activity-row">{content}</li>;
}

export function DashboardActivity({
  resumeHealth,
  summary,
}: {
  resumeHealth: DashboardResumeHealth;
  summary: DashboardSummary;
}) {
  const items = buildActivityItems(resumeHealth, summary);

  return (
    <section
      aria-labelledby="recent-activity-heading"
      className="workspace-panel min-w-0"
    >
      <div className="workspace-panel-header">
        <h2 id="recent-activity-heading">Recent activity</h2>
      </div>

      {items.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
          <span className="grid size-10 place-items-center rounded-full bg-success-soft text-success-strong">
            <CheckCircle2 aria-hidden="true" className="size-4" />
          </span>
          <p className="text-sm font-semibold text-foreground">
            No recent activity yet
          </p>
          <p className="max-w-xs text-xs leading-5 text-muted">
            Reports, applications, and review events will appear here.
          </p>
        </div>
      ) : (
        <ul className="divide-y divide-line/70">
          {items.map((item) => (
            <ActivityRow item={item} key={item.id} />
          ))}
        </ul>
      )}
    </section>
  );
}
