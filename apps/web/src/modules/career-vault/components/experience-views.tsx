import {
  ArrowDown,
  ArrowUp,
  CalendarRange,
  GitBranch,
  Pencil,
  ShieldQuestion,
  Trash2,
} from "lucide-react";

import { Badge, Button, Card, EmptyState } from "@careeros/ui";

import type { Experience } from "../api/types";
import { ProvenanceList } from "./evidence-semantics";

function monthLabel(value: string | null): string {
  if (!value) return "Present";
  const [year, month] = value.split("-").map(Number);
  if (!year || !month) return value;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    timeZone: "UTC",
    year: "numeric",
  }).format(new Date(Date.UTC(year, month - 1, 1)));
}

function months(value: string): number | undefined {
  const match = /^(\d{4})-(\d{2})$/.exec(value);
  if (!match) return undefined;
  return Number(match[1]) * 12 + Number(match[2]);
}

function gapBetween(newer: Experience, older: Experience): number | undefined {
  if (!older.endDate) return undefined;
  const end = months(older.endDate);
  const start = months(newer.startDate);
  if (end === undefined || start === undefined) return undefined;
  const gap = start - end - 1;
  return gap > 0 ? gap : undefined;
}

function ExperienceCard({
  experience,
  index,
  length,
  onDelete,
  onEdit,
  onMove,
}: {
  experience: Experience;
  index: number;
  length: number;
  onDelete: (value: Experience) => void;
  onEdit: (value: Experience) => void;
  onMove: (index: number, direction: -1 | 1) => void;
}) {
  const title = experience.displayTitle || experience.officialTitle;
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-extrabold text-foreground">{title}</h3>
          <p className="mt-1 text-sm font-bold text-muted">
            {experience.employer}
          </p>
          {experience.displayTitle && (
            <p className="mt-1 text-xs text-muted">
              Official title: {experience.officialTitle}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={experience.userConfirmed ? "success" : "warning"}>
            {experience.userConfirmed
              ? "User confirmed"
              : "Confirmation needed"}
          </Badge>
          {experience.promotionGroupId && (
            <Badge tone="primary">Promotion group</Badge>
          )}
          {experience.concurrentGroupId && (
            <Badge tone="neutral">Concurrent role</Badge>
          )}
        </div>
      </div>
      <p className="mt-3 flex items-center gap-2 text-sm text-muted">
        <CalendarRange aria-hidden="true" className="size-4" />
        <time dateTime={experience.startDate}>
          {monthLabel(experience.startDate)}
        </time>
        <span aria-hidden="true">–</span>
        {experience.endDate ? (
          <time dateTime={experience.endDate}>
            {monthLabel(experience.endDate)}
          </time>
        ) : (
          <span>Present</span>
        )}
      </p>
      {experience.location && (
        <p className="mt-2 text-sm text-muted">{experience.location}</p>
      )}
      {experience.description && (
        <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-foreground">
          {experience.description}
        </p>
      )}
      {experience.conflicts.length > 0 && (
        <div className="mt-4 rounded-xl border border-amber-200 bg-warning-soft p-3">
          <p className="flex items-center gap-2 text-sm font-extrabold text-warning-strong">
            <ShieldQuestion aria-hidden="true" className="size-4" /> Conflict
            review needed
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-warning-strong">
            {experience.conflicts.map((conflict) => (
              <li key={conflict.id}>{conflict.message}</li>
            ))}
          </ul>
        </div>
      )}
      {experience.provenance.length > 0 && (
        <details className="mt-4 rounded-xl border border-line p-3">
          <summary className="min-h-10 cursor-pointer py-2 text-sm font-bold text-primary">
            View source provenance
          </summary>
          <div className="mt-3">
            <ProvenanceList values={experience.provenance} />
          </div>
        </details>
      )}
      <div className="mt-5 flex flex-wrap gap-2 border-t border-line pt-4">
        <Button
          aria-label={`Move ${title} up`}
          disabled={index === 0}
          onClick={() => onMove(index, -1)}
          variant="ghost"
        >
          <ArrowUp aria-hidden="true" className="size-4" /> Move up
        </Button>
        <Button
          aria-label={`Move ${title} down`}
          disabled={index === length - 1}
          onClick={() => onMove(index, 1)}
          variant="ghost"
        >
          <ArrowDown aria-hidden="true" className="size-4" /> Move down
        </Button>
        <Button onClick={() => onEdit(experience)} variant="secondary">
          <Pencil aria-hidden="true" className="size-4" /> Edit
        </Button>
        <Button
          aria-label={`Delete ${title} at ${experience.employer}`}
          onClick={() => onDelete(experience)}
          variant="ghost"
        >
          <Trash2 aria-hidden="true" className="size-4" /> Delete
        </Button>
      </div>
    </Card>
  );
}

export function ExperienceList(props: {
  experiences: Experience[];
  onDelete: (value: Experience) => void;
  onEdit: (value: Experience) => void;
  onMove: (index: number, direction: -1 | 1) => void;
}) {
  if (props.experiences.length === 0) {
    return (
      <EmptyState
        description="Add career data directly. A resume is optional and will never overwrite this profile."
        title="No employment history yet"
      />
    );
  }
  return (
    <ul className="space-y-4" aria-label="Employment history list">
      {props.experiences.map((experience, index) => (
        <li key={experience.id}>
          <ExperienceCard
            experience={experience}
            index={index}
            length={props.experiences.length}
            onDelete={props.onDelete}
            onEdit={props.onEdit}
            onMove={props.onMove}
          />
        </li>
      ))}
    </ul>
  );
}

export function CareerTimeline({ experiences }: { experiences: Experience[] }) {
  if (experiences.length === 0) {
    return (
      <EmptyState
        description="Your timeline begins when you add a role. You do not need to upload a resume."
        title="Your career timeline is empty"
      />
    );
  }
  return (
    <ol
      className="relative space-y-4 border-l-2 border-primary/15 pl-7"
      aria-label="Career timeline"
    >
      {experiences.map((experience, index) => {
        const gap =
          index < experiences.length - 1
            ? gapBetween(experience, experiences[index + 1]!)
            : undefined;
        return (
          <li className="relative" key={experience.id}>
            <span
              aria-hidden="true"
              className="absolute -left-[2.15rem] top-5 size-3 rounded-full bg-primary ring-4 ring-primary-soft"
            />
            <Card className="p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="font-extrabold">
                    {experience.displayTitle || experience.officialTitle}
                  </h3>
                  <p className="mt-1 text-sm text-muted">
                    {experience.employer}
                  </p>
                </div>
                <p className="text-xs font-bold text-muted">
                  {monthLabel(experience.startDate)} –{" "}
                  {monthLabel(experience.endDate)}
                </p>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {experience.promotionGroupId && (
                  <Badge tone="primary">
                    <GitBranch aria-hidden="true" className="size-3" />{" "}
                    Promotion
                  </Badge>
                )}
                {experience.concurrentGroupId && (
                  <Badge tone="neutral">Concurrent role</Badge>
                )}
              </div>
            </Card>
            {gap && (
              <div
                className="my-4 rounded-xl border border-line bg-slate-50 p-3 text-xs leading-5 text-muted"
                role="note"
              >
                {gap} {gap === 1 ? "month" : "months"} between recorded roles.
                This is shown neutrally and is not a negative assessment.
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
