"use client";

import { Pencil, Star, Trash2 } from "lucide-react";
import { Fragment, useState } from "react";

import { Button, Select, cn } from "@rezumi/ui";

import type {
  CareerItem,
  CareerRelationship,
  Experience,
  PersonalFact,
} from "../api/types";
import { ProvenanceList } from "./evidence-semantics";
import { monthLabel } from "./experience-views";
import { factKindLabels } from "./personal-fact-form";
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
  type RowMenuItem,
} from "./profile-record-ui";

const itemKindLabels: Record<CareerItem["kind"], string> = {
  award: "Award",
  credential: "Credential",
  education: "Education",
  language: "Language",
  portfolio_link: "Portfolio link",
  project: "Project",
  publication: "Publication",
  volunteering: "Volunteering",
};

const contactColumns = [
  { className: "w-20", key: "type", label: "Type" },
  { className: "min-w-[12rem]", key: "detail", label: "Detail" },
  { className: "w-16", key: "primary", label: "Primary" },
  { className: "w-32", key: "status", label: "Status" },
  { className: "w-28", key: "provenance", label: "Provenance" },
  { className: "w-28", key: "actions", label: "Actions" },
] as const;

export function ContactFactsTable({
  facts,
  onConfirm,
  onDelete,
  onEdit,
  onEnrich,
  onSetPrimary,
  saving,
}: {
  facts: PersonalFact[];
  onConfirm: (fact: PersonalFact) => void;
  onDelete: (fact: PersonalFact) => void;
  onEdit: (fact: PersonalFact) => void;
  onEnrich: (fact: PersonalFact) => void;
  onSetPrimary: (fact: PersonalFact, primary: boolean) => void;
  saving: boolean;
}) {
  const [expandedId, setExpandedId] = useState<string>();

  return (
    <RecordTable columns={contactColumns}>
      <tbody>
        {facts.length === 0 && (
          <EmptyRecordRow colSpan={contactColumns.length}>
            No contact facts yet. Add only the contact details you want in your
            structured career record.
          </EmptyRecordRow>
        )}
        {facts.map((fact) => {
          const kind = factKindLabels[fact.kind];
          const confirmed = fact.confirmation === "confirmed";
          const expanded = expandedId === fact.id;
          const menuItems: RowMenuItem[] = [];
          if (!confirmed) {
            menuItems.push({
              label: "Confirm current value",
              onSelect: () => onConfirm(fact),
            });
          }
          if (fact.kind === "link") {
            menuItems.push({
              disabled: saving,
              label: "Import public achievements",
              onSelect: () => onEnrich(fact),
            });
          }
          return (
            <Fragment key={fact.id}>
              <RecordRow>
                <RecordCell className="font-semibold text-foreground">
                  {kind}
                </RecordCell>
                <RecordCell className="break-words text-muted-strong">
                  {fact.value}
                  {fact.label && (
                    <span className="ml-2 text-muted">({fact.label})</span>
                  )}
                </RecordCell>
                <RecordCell>
                  <button
                    aria-label={
                      fact.isPrimary
                        ? `Remove ${kind} as the primary value`
                        : `Use this ${kind} as the primary value`
                    }
                    aria-pressed={fact.isPrimary}
                    className="grid size-8 place-items-center rounded-[var(--radius-control)] transition-colors hover:bg-surface-inset disabled:cursor-not-allowed disabled:opacity-45"
                    disabled={saving}
                    onClick={() => onSetPrimary(fact, !fact.isPrimary)}
                    title={fact.isPrimary ? "Primary value" : "Set as primary"}
                    type="button"
                  >
                    <Star
                      aria-hidden="true"
                      className={cn(
                        "size-4",
                        fact.isPrimary
                          ? "fill-foreground text-foreground"
                          : "text-muted",
                      )}
                    />
                  </button>
                </RecordCell>
                <RecordCell>
                  <ConfirmationStatus confirmed={confirmed} />
                </RecordCell>
                <RecordCell className="text-muted-strong">
                  {fact.provenance.length === 0 ? (
                    <span>Manual</span>
                  ) : (
                    <RowLink
                      expanded={expanded}
                      label={`View provenance for the ${kind} contact fact`}
                      onClick={() =>
                        setExpandedId(expanded ? undefined : fact.id)
                      }
                    >
                      {provenanceSummary(fact.provenance)}
                    </RowLink>
                  )}
                </RecordCell>
                <RecordCell>
                  <div className="flex items-center gap-1">
                    <IconAction
                      icon={Pencil}
                      label={`Edit the ${kind} contact fact`}
                      onClick={() => onEdit(fact)}
                    />
                    <IconAction
                      icon={Trash2}
                      label={`Delete the ${kind} contact fact`}
                      onClick={() => onDelete(fact)}
                      tone="danger"
                    />
                    <RowMenu
                      items={menuItems}
                      label={`More actions for the ${kind} contact fact`}
                    />
                  </div>
                </RecordCell>
              </RecordRow>
              {expanded && (
                <DetailRow colSpan={contactColumns.length}>
                  <ProvenanceList values={fact.provenance} />
                </DetailRow>
              )}
            </Fragment>
          );
        })}
      </tbody>
    </RecordTable>
  );
}

const itemColumns = [
  { className: "w-20", key: "type", label: "Type" },
  { className: "min-w-[9rem]", key: "title", label: "Title" },
  { className: "min-w-[12rem]", key: "details", label: "Details" },
  { className: "w-28", key: "period", label: "Period" },
  { className: "w-36", key: "actions", label: "Actions" },
] as const;

function periodLabel(item: CareerItem): string {
  if (!item.startDate && !item.endDate) return "—";
  const start = item.startDate ? monthLabel(item.startDate) : "Start not added";
  const end = item.endDate ? monthLabel(item.endDate) : "Present";
  return `${start} – ${end}`;
}

export function CareerItemsTable({
  experiences,
  items,
  onConfirm,
  onDelete,
  onEdit,
  onLinkProject,
  onUnlinkProject,
  relationships,
  saving,
}: {
  experiences: Experience[];
  items: CareerItem[];
  onConfirm: (item: CareerItem) => void;
  onDelete: (item: CareerItem) => void;
  onEdit: (item: CareerItem) => void;
  onLinkProject: (item: CareerItem, experienceId: string) => void;
  onUnlinkProject: (relationship: CareerRelationship) => void;
  relationships: CareerRelationship[];
  saving: boolean;
}) {
  const [expandedId, setExpandedId] = useState<string>();
  const [linkTarget, setLinkTarget] = useState<Record<string, string>>({});

  return (
    <RecordTable columns={itemColumns}>
      <tbody>
        {items.length === 0 && (
          <EmptyRecordRow colSpan={itemColumns.length}>
            No education, projects, credentials, publications, awards,
            volunteering, languages, or portfolio links recorded yet.
          </EmptyRecordRow>
        )}
        {items.map((item) => {
          const expanded = expandedId === item.id;
          const linked = relationships.filter(
            (relationship) => relationship.projectId === item.id,
          );
          return (
            <Fragment key={item.id}>
              <RecordRow>
                <RecordCell className="whitespace-nowrap text-muted-strong">
                  {itemKindLabels[item.kind]}
                </RecordCell>
                <RecordCell className="font-semibold text-foreground">
                  {item.title}
                </RecordCell>
                <RecordCell className="text-muted-strong">
                  <span className="line-clamp-2">
                    {item.description ||
                      item.organization ||
                      "No details added"}
                  </span>
                </RecordCell>
                <RecordCell className="whitespace-nowrap text-muted-strong">
                  {periodLabel(item)}
                </RecordCell>
                <RecordCell>
                  <div className="flex items-center gap-1">
                    <RowLink
                      expanded={expanded}
                      label={`View record for ${item.title}`}
                      onClick={() =>
                        setExpandedId(expanded ? undefined : item.id)
                      }
                    >
                      View record
                    </RowLink>
                    <IconAction
                      icon={Pencil}
                      label={`Edit ${item.title}`}
                      onClick={() => onEdit(item)}
                    />
                    <RowMenu
                      items={[
                        {
                          disabled: item.userConfirmed,
                          label: "Confirm current facts",
                          onSelect: () => onConfirm(item),
                        },
                        {
                          label: "Delete record",
                          onSelect: () => onDelete(item),
                          tone: "danger",
                        },
                      ]}
                      label={`More actions for ${item.title}`}
                    />
                  </div>
                </RecordCell>
              </RecordRow>
              {expanded && (
                <DetailRow colSpan={itemColumns.length}>
                  <dl className="grid gap-4 sm:grid-cols-2">
                    <DetailField label="Organization">
                      {item.organization || "Not added"}
                    </DetailField>
                    <DetailField label="Source">
                      {provenanceSummary(item.provenance)}
                    </DetailField>
                    <div className="sm:col-span-2">
                      <DetailField label="Description">
                        {item.description || "Not added"}
                      </DetailField>
                    </div>
                    {item.url && (
                      <div className="sm:col-span-2">
                        <DetailField label="Saved link">
                          <a
                            className="font-semibold text-info hover:underline"
                            href={item.url}
                            rel="noreferrer"
                            target="_blank"
                          >
                            {item.url}
                            <span className="sr-only">
                              {" "}
                              (opens in a new tab)
                            </span>
                          </a>
                        </DetailField>
                      </div>
                    )}
                  </dl>
                  <div className="mt-4 flex flex-wrap items-center gap-3">
                    <ConfirmationStatus confirmed={item.userConfirmed} />
                    {!item.userConfirmed && (
                      <button
                        className="text-[0.8125rem] font-semibold text-info hover:underline"
                        onClick={() => onConfirm(item)}
                        type="button"
                      >
                        Confirm current facts
                      </button>
                    )}
                  </div>
                  {item.kind === "project" && (
                    <div className="mt-4 rounded-[var(--radius-control)] border border-line bg-surface p-3">
                      <p className="text-[0.8125rem] font-bold text-foreground">
                        Related employment
                      </p>
                      {linked.length === 0 ? (
                        <p className="mt-1 text-xs text-muted">
                          No employment relationship recorded.
                        </p>
                      ) : (
                        <ul className="mt-2 space-y-1.5">
                          {linked.map((relationship) => {
                            const experience = experiences.find(
                              (candidate) =>
                                candidate.id === relationship.experienceId,
                            );
                            return (
                              <li
                                className="flex flex-wrap items-center justify-between gap-2 text-[0.8125rem]"
                                key={relationship.id}
                              >
                                <span>
                                  {experience
                                    ? `${experience.displayTitle ?? experience.officialTitle} at ${experience.employer}`
                                    : "Related employment"}
                                </span>
                                <button
                                  className="text-[0.8125rem] font-semibold text-danger hover:underline"
                                  onClick={() => onUnlinkProject(relationship)}
                                  type="button"
                                >
                                  Remove link
                                </button>
                              </li>
                            );
                          })}
                        </ul>
                      )}
                      {experiences.length > 0 && (
                        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                          <Select
                            aria-label={`Experience to link to ${item.title}`}
                            onChange={(event) =>
                              setLinkTarget((current) => ({
                                ...current,
                                [item.id]: event.target.value,
                              }))
                            }
                            value={linkTarget[item.id] ?? ""}
                          >
                            <option value="">Choose experience</option>
                            {experiences.map((experience) => (
                              <option key={experience.id} value={experience.id}>
                                {experience.displayTitle ??
                                  experience.officialTitle}{" "}
                                at {experience.employer}
                              </option>
                            ))}
                          </Select>
                          <Button
                            disabled={!linkTarget[item.id] || saving}
                            onClick={() =>
                              onLinkProject(item, linkTarget[item.id] ?? "")
                            }
                            variant="secondary"
                          >
                            Link experience
                          </Button>
                        </div>
                      )}
                    </div>
                  )}
                  {item.provenance.length > 0 && (
                    <div className="mt-4">
                      <ProvenanceList values={item.provenance} />
                    </div>
                  )}
                </DetailRow>
              )}
            </Fragment>
          );
        })}
      </tbody>
    </RecordTable>
  );
}
