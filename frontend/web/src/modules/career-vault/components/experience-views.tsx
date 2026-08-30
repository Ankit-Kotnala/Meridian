"use client";

import { GripVertical, Pencil, TriangleAlert } from "lucide-react";
import { Fragment, useState, type DragEvent, type KeyboardEvent } from "react";

import { Badge } from "@rezumi/ui";

import type { Experience, ProfileConflict } from "../api/types";
import { ProvenanceList } from "./evidence-semantics";
import {
  ConfirmationStatus,
  DetailField,
  DetailRow,
  EmptyRecordRow,
  IconAction,
  RecordCell,
  RecordRow,
  RecordTable,
  RowLink,
  RowMenu,
  provenanceSummary,
} from "./profile-record-ui";

const employmentColumns = [
  { className: "w-9 pr-0", key: "handle", label: "Reorder", srOnly: true },
  { key: "company", label: "Company" },
  { key: "role", label: "Role" },
  { key: "dates", label: "Dates" },
  { className: "w-44", key: "actions", label: "Actions" },
] as const;

const conflictLabels: Record<string, string> = {
  concurrent_current_role: "Concurrent roles",
  concurrent_roles_observed: "Concurrent roles",
  grouped_promotion_sequence: "Promotion sequence",
  same_employer_overlap_needs_review: "Date conflict",
  timeline_gap_observed: "Timeline gap",
};

function conflictLabel(conflict: ProfileConflict): string {
  return (
    conflictLabels[conflict.code] ??
    conflict.code
      .replaceAll("_", " ")
      .replace(/^./, (part) => part.toUpperCase())
  );
}

/**
 * Month-and-year precision only. A source that recorded a year without a month
 * is rendered exactly as stored rather than being widened to January.
 */
export function monthLabel(value: string | null): string {
  if (!value) return "Present";
  const [year, month] = value.split("-").map(Number);
  if (!year || !month) return value;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    timeZone: "UTC",
    year: "numeric",
  }).format(new Date(Date.UTC(year, month - 1, 1)));
}

function employmentTypeLabel(value: string | null): string {
  if (!value) return "Not added";
  return value.replaceAll("_", " ").replace(/^./, (part) => part.toUpperCase());
}

export function EmploymentTable({
  experiences,
  onConfirm,
  onDelete,
  onEdit,
  onReorder,
}: {
  experiences: Experience[];
  onConfirm: (value: Experience) => void;
  onDelete: (value: Experience) => void;
  onEdit: (value: Experience) => void;
  onReorder: (from: number, to: number) => void;
}) {
  const [expandedId, setExpandedId] = useState<string>();
  const [draggingIndex, setDraggingIndex] = useState<number>();

  const conflicts = new Map<string, ProfileConflict>();
  for (const experience of experiences) {
    for (const conflict of experience.conflicts) {
      conflicts.set(conflict.id, conflict);
    }
  }

  function handleDrop(event: DragEvent<HTMLTableRowElement>, target: number) {
    event.preventDefault();
    if (draggingIndex !== undefined) onReorder(draggingIndex, target);
    setDraggingIndex(undefined);
  }

  function handleHandleKeyDown(
    event: KeyboardEvent<HTMLButtonElement>,
    index: number,
  ) {
    if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
    event.preventDefault();
    onReorder(index, index + (event.key === "ArrowUp" ? -1 : 1));
  }

  return (
    <RecordTable columns={employmentColumns}>
      <tbody>
        {experiences.length === 0 && (
          <EmptyRecordRow colSpan={employmentColumns.length}>
            No employment recorded yet. A resume is optional — you can add roles
            directly.
          </EmptyRecordRow>
        )}
        {experiences.map((experience, index) => {
          const title = experience.displayTitle || experience.officialTitle;
          const expanded = expandedId === experience.id;
          return (
            <Fragment key={experience.id}>
              <RecordRow
                className={draggingIndex === index ? "opacity-50" : undefined}
                draggable
                onDragEnd={() => setDraggingIndex(undefined)}
                onDragOver={(event) => event.preventDefault()}
                onDragStart={() => setDraggingIndex(index)}
                onDrop={(event) => handleDrop(event, index)}
              >
                <RecordCell className="w-9 pr-0">
                  <button
                    aria-label={`Reorder ${title} at ${experience.employer}. Use the arrow keys to move it.`}
                    className="grid size-7 cursor-grab place-items-center rounded-[var(--radius-control)] text-muted hover:bg-surface-inset hover:text-foreground active:cursor-grabbing"
                    onKeyDown={(event) => handleHandleKeyDown(event, index)}
                    type="button"
                  >
                    <GripVertical aria-hidden="true" className="size-4" />
                  </button>
                </RecordCell>
                <RecordCell className="font-semibold text-foreground">
                  {experience.employer}
                </RecordCell>
                <RecordCell className="font-semibold text-foreground">
                  {title}
                  {experience.promotionGroupId && (
                    <Badge className="ml-2" tone="primary">
                      Promotion
                    </Badge>
                  )}
                  {experience.concurrentGroupId && (
                    <Badge className="ml-2" tone="neutral">
                      Concurrent
                    </Badge>
                  )}
                </RecordCell>
                <RecordCell className="whitespace-nowrap text-muted-strong">
                  <time dateTime={experience.startDate}>
                    {monthLabel(experience.startDate)}
                  </time>
                  <span aria-hidden="true"> – </span>
                  {experience.endDate ? (
                    <time dateTime={experience.endDate}>
                      {monthLabel(experience.endDate)}
                    </time>
                  ) : (
                    <span>Present</span>
                  )}
                </RecordCell>
                <RecordCell>
                  <div className="flex items-center gap-1">
                    <RowLink
                      expanded={expanded}
                      label={`View record for ${title} at ${experience.employer}`}
                      onClick={() =>
                        setExpandedId(expanded ? undefined : experience.id)
                      }
                    >
                      View record
                    </RowLink>
                    <IconAction
                      icon={Pencil}
                      label={`Edit ${title} at ${experience.employer}`}
                      onClick={() => onEdit(experience)}
                    />
                    <RowMenu
                      items={[
                        {
                          disabled: experience.userConfirmed,
                          label: "Confirm current facts",
                          onSelect: () => onConfirm(experience),
                        },
                        {
                          disabled: index === 0,
                          label: "Move up",
                          onSelect: () => onReorder(index, index - 1),
                        },
                        {
                          disabled: index === experiences.length - 1,
                          label: "Move down",
                          onSelect: () => onReorder(index, index + 1),
                        },
                        {
                          label: "Delete employment",
                          onSelect: () => onDelete(experience),
                          tone: "danger",
                        },
                      ]}
                      label={`More actions for ${title} at ${experience.employer}`}
                    />
                  </div>
                </RecordCell>
              </RecordRow>
              {expanded && (
                <DetailRow colSpan={employmentColumns.length}>
                  <dl className="grid gap-4 sm:grid-cols-2">
                    <DetailField label="Official title">
                      {experience.officialTitle}
                    </DetailField>
                    <DetailField label="Employment type">
                      {employmentTypeLabel(experience.employmentType)}
                    </DetailField>
                    <DetailField label="Location">
                      {experience.location || "Not added"}
                    </DetailField>
                    <DetailField label="Source">
                      {provenanceSummary(experience.provenance)}
                    </DetailField>
                    <div className="sm:col-span-2">
                      <DetailField label="Description">
                        {experience.description || "Not added"}
                      </DetailField>
                    </div>
                  </dl>
                  <div className="mt-4 flex flex-wrap items-center gap-3">
                    <ConfirmationStatus confirmed={experience.userConfirmed} />
                    {!experience.userConfirmed && (
                      <button
                        className="text-[0.8125rem] font-semibold text-info hover:underline"
                        onClick={() => onConfirm(experience)}
                        type="button"
                      >
                        Confirm current facts
                      </button>
                    )}
                  </div>
                  {experience.provenance.length > 0 && (
                    <div className="mt-4">
                      <ProvenanceList values={experience.provenance} />
                    </div>
                  )}
                </DetailRow>
              )}
            </Fragment>
          );
        })}
        {[...conflicts.values()].map((conflict) => (
          <tr key={conflict.id}>
            <td className="px-4 pb-3 pt-1" colSpan={employmentColumns.length}>
              <p
                className={
                  conflict.severity === "review"
                    ? "flex flex-wrap items-center gap-x-4 gap-y-1 rounded-[var(--radius-control)] border border-danger/25 bg-danger-soft px-3 py-2 text-[0.8125rem]"
                    : "flex flex-wrap items-center gap-x-4 gap-y-1 rounded-[var(--radius-control)] border border-line bg-surface-subtle px-3 py-2 text-[0.8125rem]"
                }
                role={conflict.severity === "review" ? "alert" : undefined}
              >
                <span
                  className={
                    conflict.severity === "review"
                      ? "inline-flex items-center gap-1.5 font-bold text-danger"
                      : "inline-flex items-center gap-1.5 font-bold text-muted-strong"
                  }
                >
                  <TriangleAlert aria-hidden="true" className="size-4" />
                  {conflictLabel(conflict)}
                </span>
                <span className="text-muted-strong">{conflict.message}</span>
              </p>
            </td>
          </tr>
        ))}
      </tbody>
    </RecordTable>
  );
}
