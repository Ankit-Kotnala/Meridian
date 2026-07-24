"use client";

import { CheckSquare2, FileStack, StickyNote } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { Badge, EmptyState, cn } from "@careeros/ui";

import type {
  Application,
  ApplicationCalendar,
  ApplicationStage,
} from "../api/types";
import {
  applicationStages,
  formatDate,
  humanize,
  stageTone,
} from "./application-options";
import { ApplicationStageControl } from "./application-stage-control";

type CollectionProps = {
  applications: Application[];
  busyId?: string | undefined;
  onMove: (
    application: Application,
    stage: ApplicationStage,
    reopenReason?: string,
  ) => void;
};

function ApplicationMetadata({ application }: { application: Application }) {
  return (
    <dl className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted">
      <div>
        <dt className="font-bold">Deadline</dt>
        <dd>{formatDate(application.applicationDeadline)}</dd>
      </div>
      <div>
        <dt className="font-bold">Follow-up</dt>
        <dd>{formatDate(application.followUpAt)}</dd>
      </div>
      <div className="flex items-center gap-1">
        <CheckSquare2 aria-hidden="true" className="size-3.5" />
        <dt className="sr-only">Open tasks</dt>
        <dd>{application.openTaskCount} open</dd>
      </div>
      <div className="flex items-center gap-1">
        <FileStack aria-hidden="true" className="size-3.5" />
        <dt className="sr-only">Application packs</dt>
        <dd>{application.packCount} packs</dd>
      </div>
    </dl>
  );
}

function ApplicationCard({
  application,
  busy,
  onMove,
}: {
  application: Application;
  busy: boolean;
  onMove: CollectionProps["onMove"];
}) {
  return (
    <article className="rounded-xl border border-line bg-white p-3 shadow-sm">
      <Link
        className="block rounded-lg outline-none focus-visible:ring-3 focus-visible:ring-primary-soft"
        href={`/applications/${application.id}`}
      >
        <h3 className="text-sm font-black text-foreground">
          {application.jobTitle}
        </h3>
        <p className="mt-1 text-xs text-muted">
          {[application.company, application.location]
            .filter(Boolean)
            .join(" · ") || "Company and location not recorded"}
        </p>
      </Link>
      <ApplicationMetadata application={application} />
      <div className="mt-3">
        <ApplicationStageControl
          application={application}
          busy={busy}
          compact
          key={`${application.id}-${application.version}`}
          onMove={onMove}
        />
      </div>
    </article>
  );
}

export function ApplicationBoard({
  applications,
  busyId,
  onMove,
}: CollectionProps) {
  return (
    <section aria-label="Applications Kanban board">
      <p className="sr-only">
        Use each application card&apos;s stage selector and Move button as the
        keyboard-accessible alternative to dragging.
      </p>
      <div className="overflow-x-auto pb-4">
        <div className="grid min-w-max auto-cols-[18rem] grid-flow-col gap-4">
          {applicationStages.map((stage) => {
            const items = applications.filter(
              (application) => application.stage === stage,
            );
            return (
              <section
                aria-labelledby={`stage-${stage}`}
                className="rounded-xl bg-slate-100/80 p-3"
                key={stage}
              >
                <div className="mb-3 flex items-center justify-between gap-3">
                  <h2
                    className="text-sm font-black text-foreground"
                    id={`stage-${stage}`}
                  >
                    {humanize(stage)}
                  </h2>
                  <Badge tone={stageTone(stage)}>{items.length}</Badge>
                </div>
                {items.length ? (
                  <ul className="space-y-3">
                    {items.map((application) => (
                      <li key={application.id}>
                        <ApplicationCard
                          application={application}
                          busy={busyId === application.id}
                          onMove={onMove}
                        />
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="rounded-lg border border-dashed border-line bg-white/70 p-3 text-xs text-muted">
                    No applications in this stage.
                  </p>
                )}
              </section>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export function ApplicationTable({
  applications,
  busyId,
  onMove,
}: CollectionProps) {
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-white shadow-sm">
      <table className="min-w-[70rem] text-left text-sm">
        <caption className="sr-only">
          Applications with stage, pinned resume version, dates, and actions
        </caption>
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-muted">
          <tr>
            <th className="px-4 py-3" scope="col">
              Opportunity
            </th>
            <th className="px-4 py-3" scope="col">
              Stage
            </th>
            <th className="px-4 py-3" scope="col">
              Resume
            </th>
            <th className="px-4 py-3" scope="col">
              Deadline
            </th>
            <th className="px-4 py-3" scope="col">
              Follow-up
            </th>
            <th className="px-4 py-3" scope="col">
              Activity
            </th>
            <th className="px-4 py-3" scope="col">
              Move stage
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {applications.map((application) => (
            <tr key={application.id}>
              <th className="px-4 py-4 align-top" scope="row">
                <Link
                  className="font-black text-foreground hover:text-primary"
                  href={`/applications/${application.id}`}
                >
                  {application.jobTitle}
                </Link>
                <span className="mt-1 block text-xs font-normal text-muted">
                  {[application.company, application.location]
                    .filter(Boolean)
                    .join(" · ") || "Details not recorded"}
                </span>
              </th>
              <td className="px-4 py-4 align-top">
                <Badge tone={stageTone(application.stage)}>
                  {humanize(application.stage)}
                </Badge>
              </td>
              <td className="px-4 py-4 align-top">
                <span className="font-bold text-foreground">
                  {application.resumeTitle}
                </span>
                <span className="block text-xs text-muted">
                  Version {application.resumeVersionNumber}
                </span>
              </td>
              <td className="px-4 py-4 align-top text-muted">
                {formatDate(application.applicationDeadline)}
              </td>
              <td className="px-4 py-4 align-top text-muted">
                {formatDate(application.followUpAt)}
              </td>
              <td className="px-4 py-4 align-top text-xs text-muted">
                <span className="flex items-center gap-1">
                  <CheckSquare2 aria-hidden="true" className="size-3.5" />
                  {application.openTaskCount} open tasks
                </span>
                <span className="mt-1 flex items-center gap-1">
                  <StickyNote aria-hidden="true" className="size-3.5" />
                  {application.noteCount} notes
                </span>
              </td>
              <td className="px-4 py-4 align-top">
                <ApplicationStageControl
                  application={application}
                  busy={busyId === application.id}
                  compact
                  key={`${application.id}-${application.version}`}
                  onMove={onMove}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ApplicationAgenda({
  calendar,
}: {
  calendar: ApplicationCalendar;
}) {
  const grouped = useMemo(() => {
    const result = new Map<string, ApplicationCalendar["data"]>();
    for (const item of calendar.data) {
      const items = result.get(item.onDate) ?? [];
      items.push(item);
      result.set(item.onDate, items);
    }
    return [...result.entries()].sort(([left], [right]) =>
      left.localeCompare(right),
    );
  }, [calendar.data]);

  if (!grouped.length) {
    return (
      <EmptyState
        description="Add a deadline, follow-up date, or task due date to see it in this month."
        title="Nothing scheduled"
      />
    );
  }

  return (
    <section aria-label="Application calendar agenda" className="space-y-4">
      {grouped.map(([date, items]) => (
        <section
          aria-labelledby={`agenda-${date}`}
          className="rounded-xl border border-line bg-white shadow-sm"
          key={date}
        >
          <h2
            className="border-b border-line px-4 py-3 text-sm font-black text-foreground"
            id={`agenda-${date}`}
          >
            {formatDate(date)}
          </h2>
          <ul className="divide-y divide-line">
            {items.map((item) => (
              <li
                className={cn(
                  "flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between",
                  item.completed && "opacity-60",
                )}
                key={item.id}
              >
                <div className="min-w-0">
                  <Link
                    className="font-bold text-foreground hover:text-primary"
                    href={`/applications/${item.applicationId}`}
                  >
                    {item.title}
                  </Link>
                  <p className="text-xs text-muted">{humanize(item.kind)}</p>
                </div>
                <Badge tone={item.completed ? "success" : "neutral"}>
                  {item.completed ? "Completed" : humanize(item.kind)}
                </Badge>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </section>
  );
}

export function ApplicationCollectionEmpty({
  filtered,
}: {
  filtered: boolean;
}) {
  return (
    <EmptyState
      description={
        filtered
          ? "Adjust or clear the current search and stage filters."
          : "Add a saved job and pin the exact resume version you plan to use."
      }
      title={filtered ? "No matching applications" : "No applications yet"}
    />
  );
}
