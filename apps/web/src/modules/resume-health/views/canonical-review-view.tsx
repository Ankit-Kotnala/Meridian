"use client";

import { Check, FileCheck2, Plus, RefreshCcw, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import {
  Alert,
  Badge,
  Button,
  Card,
  cn,
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  Tabs,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  ApiRequestError,
  getDocument,
  getPlainText,
  getReadingOrder,
  newIdempotencyKey,
  startResumeHealth,
  updateCanonicalResume,
} from "../api/resume-health-api";
import type {
  CanonicalResume,
  DocumentDetail,
  PlainText,
  ReadingOrder,
  ResumeHealthAccess,
  SemanticEntity,
  SemanticReviewOperation,
} from "../api/types";

const semanticFieldNames = {
  contact: ["name", "email", "phone", "location", "link"],
  experience: [
    "employer",
    "title",
    "start_date",
    "end_date",
    "location",
    "employment_type",
    "description",
    "achievement",
  ],
  education: [
    "institution",
    "degree",
    "field",
    "start_date",
    "end_date",
    "location",
  ],
  project: ["name", "description", "start_date", "end_date", "skill", "link"],
  skill: ["name", "category"],
  certification: [
    "name",
    "issuer",
    "issued_date",
    "expires_date",
    "credential_id",
    "link",
  ],
} as const;

type SemanticKind = keyof typeof semanticFieldNames;
type DatePrecision = "day" | "month" | "year" | "unknown";

function semanticFieldType(name: string) {
  if (name.includes("date")) return "date" as const;
  if (name === "email") return "email" as const;
  if (name === "phone") return "phone" as const;
  if (name === "link") return "url" as const;
  if (name === "achievement") return "bullet" as const;
  return "text" as const;
}

function semanticFieldNamesForType(
  kind: SemanticKind,
  fieldType: ReturnType<typeof semanticFieldType>,
) {
  return semanticFieldNames[kind].filter((name) => {
    if (name === "description") {
      return fieldType === "text" || fieldType === "bullet";
    }
    return semanticFieldType(name) === fieldType;
  });
}

function confidence(value: number) {
  if (value >= 85)
    return { label: `High confidence, ${value}%`, tone: "success" as const };
  if (value >= 60)
    return { label: `Review recommended, ${value}%`, tone: "warning" as const };
  return { label: `Low confidence, ${value}%`, tone: "danger" as const };
}

function SemanticAddFieldForm({
  entity,
  onAdd,
}: {
  entity: SemanticEntity;
  onAdd: (operation: SemanticReviewOperation) => void;
}) {
  const [name, setName] = useState<string>(semanticFieldNames[entity.kind][0]);
  const [value, setValue] = useState("");
  const [datePrecision, setDatePrecision] = useState<DatePrecision>("unknown");
  const fieldType = semanticFieldType(name);
  return (
    <div className="grid gap-3 border-t border-line bg-surface-subtle p-4 sm:grid-cols-[minmax(9rem,0.4fr)_1fr_auto]">
      <label className="text-xs font-bold text-muted">
        Fact type
        <select
          className="mt-1 block w-full rounded-lg border border-line bg-surface px-2 py-2 text-sm text-foreground"
          onChange={(event) => setName(event.target.value)}
          value={name}
        >
          {semanticFieldNames[entity.kind].map((fieldName) => (
            <option key={fieldName} value={fieldName}>
              {fieldName.replaceAll("_", " ")}
            </option>
          ))}
        </select>
      </label>
      <label className="text-xs font-bold text-muted">
        User-confirmed value
        <input
          className="mt-1 block w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-foreground"
          maxLength={10_000}
          onChange={(event) => setValue(event.target.value)}
          value={value}
        />
      </label>
      {fieldType === "date" && (
        <label className="text-xs font-bold text-muted sm:col-start-2">
          Date precision
          <select
            className="mt-1 block w-full rounded-lg border border-line bg-surface px-2 py-2 text-sm text-foreground"
            onChange={(event) =>
              setDatePrecision(event.target.value as DatePrecision)
            }
            value={datePrecision}
          >
            <option value="day">day</option>
            <option value="month">month</option>
            <option value="year">year</option>
            <option value="unknown">unknown</option>
          </select>
        </label>
      )}
      <Button
        className="self-end"
        disabled={!value.trim()}
        onClick={() => {
          onAdd({
            operation: "addField",
            entityId: entity.id,
            name,
            fieldType,
            value: value.trim(),
            datePrecision: fieldType === "date" ? datePrecision : null,
          });
          setValue("");
          setDatePrecision("unknown");
        }}
        type="button"
        variant="secondary"
      >
        <Plus aria-hidden="true" className="size-4" /> Add fact
      </Button>
    </div>
  );
}

function SemanticAddEntityForm({
  onAdd,
}: {
  onAdd: (operation: SemanticReviewOperation) => void;
}) {
  const [kind, setKind] = useState<SemanticKind>("experience");
  const [value, setValue] = useState("");
  const name = semanticFieldNames[kind][0];
  const fieldType = semanticFieldType(name);
  return (
    <Card className="grid gap-3 p-4 sm:grid-cols-[minmax(10rem,0.4fr)_1fr_auto]">
      <label className="text-xs font-bold text-muted">
        New record type
        <select
          className="mt-1 block w-full rounded-lg border border-line bg-surface px-2 py-2 text-sm text-foreground"
          onChange={(event) => setKind(event.target.value as SemanticKind)}
          value={kind}
        >
          {Object.keys(semanticFieldNames).map((entityKind) => (
            <option key={entityKind} value={entityKind}>
              {entityKind}
            </option>
          ))}
        </select>
      </label>
      <label className="text-xs font-bold text-muted">
        {name.replaceAll("_", " ")}
        <input
          className="mt-1 block w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-foreground"
          maxLength={10_000}
          onChange={(event) => setValue(event.target.value)}
          value={value}
        />
      </label>
      <Button
        className="self-end"
        disabled={!value.trim()}
        onClick={() => {
          onAdd({
            operation: "addEntity",
            kind,
            fields: [
              {
                name,
                fieldType,
                value: value.trim(),
                datePrecision: fieldType === "date" ? "month" : null,
              },
            ],
          });
          setValue("");
        }}
        type="button"
        variant="secondary"
      >
        <Plus aria-hidden="true" className="size-4" /> Add record
      </Button>
    </Card>
  );
}

export function CanonicalReviewView({
  access,
  documentId,
}: {
  access: ResumeHealthAccess;
  documentId: string;
}) {
  const router = useRouter();
  const [document, setDocument] = useState<DocumentDetail>();
  const [canonical, setCanonical] = useState<CanonicalResume>();
  const [plainText, setPlainText] = useState<PlainText>();
  const [readingOrder, setReadingOrder] = useState<ReadingOrder>();
  const [values, setValues] = useState<Record<string, string>>({});
  const [semanticValues, setSemanticValues] = useState<Record<string, string>>(
    {},
  );
  const [datePrecisions, setDatePrecisions] = useState<
    Record<string, DatePrecision>
  >({});
  const [confirmedFields, setConfirmedFields] = useState<
    Record<string, boolean>
  >({});
  const [removedFields, setRemovedFields] = useState<Record<string, boolean>>(
    {},
  );
  const [removedEntities, setRemovedEntities] = useState<
    Record<string, boolean>
  >({});
  const [entityKinds, setEntityKinds] = useState<Record<string, SemanticKind>>(
    {},
  );
  const [fieldNames, setFieldNames] = useState<Record<string, string>>({});
  const [addedOperations, setAddedOperations] = useState<
    SemanticReviewOperation[]
  >([]);
  const [confirmNoChanges, setConfirmNoChanges] = useState(false);
  const [failure, setFailure] = useState<string>();
  const [conflict, setConflict] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setFailure(undefined);
    setConflict(false);
    try {
      const [nextDocument, nextPlainText, nextReadingOrder] = await Promise.all(
        [
          getDocument(access, documentId),
          getPlainText(access, documentId),
          getReadingOrder(access, documentId),
        ],
      );
      setDocument(nextDocument);
      setCanonical(nextDocument.canonicalResume ?? undefined);
      setPlainText(nextPlainText);
      setReadingOrder(nextReadingOrder);
      setValues(
        Object.fromEntries(
          (nextDocument.canonicalResume?.sections ?? []).flatMap((section) =>
            section.fields.map((field) => [field.id, field.value]),
          ),
        ),
      );
      setSemanticValues(
        Object.fromEntries(
          (nextDocument.canonicalResume?.semanticEntities ?? []).flatMap(
            (entity) => entity.fields.map((field) => [field.id, field.value]),
          ),
        ),
      );
      setDatePrecisions(
        Object.fromEntries(
          (nextDocument.canonicalResume?.semanticEntities ?? []).flatMap(
            (entity) =>
              entity.fields.flatMap((field) =>
                field.datePrecision
                  ? [[field.id, field.datePrecision] as const]
                  : [],
              ),
          ),
        ),
      );
      setEntityKinds(
        Object.fromEntries(
          (nextDocument.canonicalResume?.semanticEntities ?? []).map(
            (entity) => [entity.id, entity.kind],
          ),
        ),
      );
      setFieldNames(
        Object.fromEntries(
          (nextDocument.canonicalResume?.semanticEntities ?? []).flatMap(
            (entity) => entity.fields.map((field) => [field.id, field.name]),
          ),
        ),
      );
      setConfirmedFields({});
      setRemovedFields({});
      setRemovedEntities({});
      setAddedOperations([]);
      setConfirmNoChanges(false);
    } catch (error) {
      setFailure(
        requestErrorMessage(
          error,
          "We couldn’t load the parsed resume for review.",
        ),
      );
    }
  }, [access, documentId]);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  const fields = useMemo(
    () => canonical?.sections.flatMap((section) => section.fields) ?? [],
    [canonical],
  );
  const semanticEntities = canonical?.semanticEntities ?? [];

  async function saveAndAnalyze() {
    if (!canonical) return;
    setSaving(true);
    setFailure(undefined);
    setConflict(false);
    try {
      const changedFields = fields.flatMap((field) => {
        const value = (values[field.id] ?? "").trim();
        return value === field.value ? [] : [{ id: field.id, value }];
      });
      const semanticOperations: SemanticReviewOperation[] = [];
      for (const entity of semanticEntities) {
        if (removedEntities[entity.id]) {
          semanticOperations.push({
            operation: "removeEntity",
            entityId: entity.id,
          });
          continue;
        }
        const nextKind = entityKinds[entity.id] ?? entity.kind;
        if (nextKind !== entity.kind) {
          semanticOperations.push({
            operation: "reclassifyEntity",
            entityId: entity.id,
            kind: nextKind,
            fields: entity.fields.map((field) => ({
              fieldId: field.id,
              name: fieldNames[field.id] ?? field.name,
            })),
          });
        }
        for (const field of entity.fields) {
          if (removedFields[field.id]) {
            semanticOperations.push({
              operation: "removeField",
              fieldId: field.id,
            });
            continue;
          }
          const value = (semanticValues[field.id] ?? "").trim();
          if (value !== field.value) {
            semanticOperations.push({
              operation: "correctField",
              fieldId: field.id,
              value,
              datePrecision:
                field.fieldType === "date"
                  ? (datePrecisions[field.id] ?? "unknown")
                  : null,
            });
          } else if (
            confirmedFields[field.id] &&
            field.reviewState === "unreviewed"
          ) {
            semanticOperations.push({
              operation: "confirmField",
              fieldId: field.id,
            });
          }
        }
      }
      semanticOperations.push(...addedOperations);
      const semanticMode =
        canonical.semanticSchemaVersion !== null ||
        canonical.legacyUpgradeRequired;
      if (
        semanticMode &&
        semanticOperations.length === 0 &&
        changedFields.length === 0 &&
        !confirmNoChanges
      ) {
        setFailure(
          "Confirm that no changes are needed, or record at least one typed review action.",
        );
        setSaving(false);
        return;
      }
      if (
        confirmNoChanges &&
        (semanticOperations.length > 0 || changedFields.length > 0)
      ) {
        setFailure(
          "The no-change confirmation cannot be combined with review edits. Clear it or undo the edits.",
        );
        setSaving(false);
        return;
      }
      if (semanticMode && semanticOperations.length > 0) {
        const reviewed = await updateCanonicalResume(
          access,
          documentId,
          canonical.version,
          {
            fields: [],
            semanticOperations,
            confirmNoChanges: false,
          },
        );
        setCanonical(reviewed);
      } else if (changedFields.length > 0) {
        const reviewed = await updateCanonicalResume(
          access,
          documentId,
          canonical.version,
          {
            fields: changedFields,
            semanticOperations: [],
            confirmNoChanges: false,
          },
        );
        setCanonical(reviewed);
      } else if (confirmNoChanges) {
        const reviewed = await updateCanonicalResume(
          access,
          documentId,
          canonical.version,
          {
            fields: [],
            semanticOperations: [],
            confirmNoChanges: true,
          },
        );
        setCanonical(reviewed);
      }
      const accepted = await startResumeHealth(
        access,
        documentId,
        newIdempotencyKey(),
      );
      const prefix =
        access === "account"
          ? "/resume-health/account"
          : "/resume-health/guest";
      router.push(
        `${prefix}/processing/${encodeURIComponent(accepted.job.id)}`,
      );
    } catch (error) {
      if (error instanceof ApiRequestError && error.failure.status === 409) {
        setConflict(true);
        setFailure(
          "This parsed resume changed in another tab. Reload the latest version before saving your review.",
        );
      } else {
        setFailure(
          requestErrorMessage(
            error,
            "We couldn’t save your review or start the analysis.",
          ),
        );
      }
    } finally {
      setSaving(false);
    }
  }

  if (!document && !failure) {
    return (
      <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
        <LoadingSkeleton />
      </main>
    );
  }
  if (!document) {
    return (
      <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
        <ErrorState
          description={failure ?? "The parsed resume is unavailable."}
          onRetry={load}
          title="Parsed resume unavailable"
        />
      </main>
    );
  }
  if (!canonical) {
    return (
      <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
        <EmptyState
          action={
            <Button onClick={() => void load()} variant="secondary">
              <RefreshCcw aria-hidden="true" className="size-4" /> Check status
            </Button>
          }
          description="The document has not produced reviewed structured fields. It may still be processing or may need a new clean upload."
          title="No parsed fields available"
        />
      </main>
    );
  }

  const legacyStructuredPanel = (
    <div className="space-y-5 py-5">
      {canonical.sections.length === 0 ? (
        <EmptyState
          description="Rezumi could not identify reliable structured sections. Review the plain text and try a cleaner source document."
          title="No structured sections found"
        />
      ) : (
        canonical.sections.map((section, sectionIndex) => (
          <Card className="overflow-hidden" key={section.id}>
            <header className="border-b border-line bg-surface-subtle px-5 py-4">
              <h2 className="text-sm font-extrabold text-foreground">
                {section.title}
              </h2>
              <p className="mt-1 text-xs capitalize text-muted">
                {section.kind} section
              </p>
            </header>
            <div className="divide-y divide-line">
              {section.fields.map((field, fieldIndex) => {
                const presentation = confidence(field.confidence);
                const inputId = `canonical-${sectionIndex}-${fieldIndex}`;
                const sourceId = `${inputId}-source`;
                return (
                  <div className="grid gap-5 p-5 lg:grid-cols-2" key={field.id}>
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-sm font-extrabold text-foreground">
                          Extracted {field.label}
                        </h3>
                        <Badge tone={presentation.tone}>
                          {presentation.label}
                        </Badge>
                      </div>
                      <blockquote
                        className="mt-3 whitespace-pre-wrap rounded-xl border border-line bg-surface-subtle p-3 text-sm leading-6 text-muted"
                        id={sourceId}
                      >
                        {field.originalValue || "No value was extracted."}
                      </blockquote>
                      {field.sourceSpans.length > 0 && (
                        <p className="mt-2 text-xs leading-5 text-muted">
                          Source excerpt: {field.sourceSpans[0]!.excerpt}
                          {field.sourceSpans[0]!.page
                            ? ` (page ${field.sourceSpans[0]!.page})`
                            : ""}
                        </p>
                      )}
                    </div>
                    <div>
                      <label
                        className="block text-sm font-extrabold text-foreground"
                        htmlFor={inputId}
                      >
                        Reviewed {field.label}
                      </label>
                      <textarea
                        aria-describedby={sourceId}
                        className="mt-3 min-h-32 w-full resize-y rounded-xl border border-line bg-surface px-3 py-2.5 text-sm leading-6 text-foreground shadow-sm outline-none transition focus:border-primary focus:ring-3 focus:ring-primary/15"
                        id={inputId}
                        maxLength={10_000}
                        onChange={(event) =>
                          setValues((current) => ({
                            ...current,
                            [field.id]: event.target.value,
                          }))
                        }
                        value={values[field.id] ?? ""}
                      />
                      <p className="mt-2 text-xs leading-5 text-muted">
                        Correct only what the source supports. The original
                        extraction remains preserved for audit and explanation.
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        ))
      )}
    </div>
  );

  const semanticStructuredPanel = (
    <div className="space-y-5 py-5">
      {semanticEntities.length === 0 ? (
        <EmptyState
          description="No semantic records were detected. You can confirm that result or add a user-supported record below."
          title="No typed records detected"
        />
      ) : (
        semanticEntities.map((entity, entityIndex) => {
          const removed = removedEntities[entity.id] ?? false;
          const nextKind = entityKinds[entity.id] ?? entity.kind;
          const compatibleKinds = (
            Object.keys(semanticFieldNames) as SemanticKind[]
          ).filter((kind) =>
            entity.fields.every(
              (field) =>
                semanticFieldNamesForType(kind, field.fieldType).length > 0,
            ),
          );
          return (
            <Card
              className={
                removed ? "overflow-hidden opacity-60" : "overflow-hidden"
              }
              key={entity.id}
            >
              <header className="flex flex-col gap-3 border-b border-line bg-surface-subtle px-5 py-4 sm:flex-row sm:items-end sm:justify-between">
                <label className="text-xs font-bold text-muted">
                  Record classification
                  <select
                    className="mt-1 block rounded-lg border border-line bg-surface px-2 py-2 text-sm font-bold text-foreground"
                    disabled={removed}
                    onChange={(event) => {
                      const kind = event.target.value as SemanticKind;
                      setAddedOperations((current) =>
                        current.filter(
                          (operation) =>
                            operation.operation !== "addField" ||
                            operation.entityId !== entity.id,
                        ),
                      );
                      setEntityKinds((current) => ({
                        ...current,
                        [entity.id]: kind,
                      }));
                      setFieldNames((current) => {
                        const next = { ...current };
                        entity.fields.forEach((field, index) => {
                          const allowed = semanticFieldNamesForType(
                            kind,
                            field.fieldType,
                          );
                          const existing = next[field.id] ?? field.name;
                          next[field.id] = allowed.includes(
                            existing as (typeof allowed)[number],
                          )
                            ? existing
                            : allowed[index % allowed.length]!;
                        });
                        return next;
                      });
                    }}
                    value={nextKind}
                  >
                    {compatibleKinds.map((kind) => (
                      <option key={kind} value={kind}>
                        {kind}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="flex items-center gap-2">
                  <Badge
                    tone={
                      entity.reviewState === "unreviewed"
                        ? "warning"
                        : entity.reviewState === "removed"
                          ? "danger"
                          : "success"
                    }
                  >
                    {entity.reviewState.replaceAll("_", " ")}
                  </Badge>
                  <Button
                    onClick={() => {
                      setAddedOperations((current) =>
                        current.filter(
                          (operation) =>
                            operation.operation !== "addField" ||
                            operation.entityId !== entity.id,
                        ),
                      );
                      setRemovedEntities((current) => ({
                        ...current,
                        [entity.id]: !removed,
                      }));
                    }}
                    type="button"
                    variant="secondary"
                  >
                    <Trash2 aria-hidden="true" className="size-4" />
                    {removed ? "Undo remove" : "Remove record"}
                  </Button>
                </div>
              </header>
              {nextKind === "skill" ? (
                <div className="flex flex-wrap gap-2 p-5">
                  {entity.fields.map((field, fieldIndex) => {
                    const fieldRemoved = removedFields[field.id] ?? false;
                    const confirmed = confirmedFields[field.id] ?? false;
                    const chipSourceId = `semantic-${entityIndex}-${fieldIndex}-source`;
                    const skillValue = semanticValues[field.id] ?? "";
                    return (
                      <span
                        className={cn(
                          "group inline-flex items-center gap-1.5 rounded-full border py-1 pl-3 pr-1.5 text-sm transition-colors",
                          fieldRemoved
                            ? "border-line bg-surface-subtle text-muted line-through"
                            : confirmed || field.reviewState !== "unreviewed"
                              ? "border-primary/40 bg-primary-soft/50 text-foreground"
                              : "border-line bg-surface text-foreground",
                        )}
                        key={field.id}
                      >
                        <input
                          aria-describedby={chipSourceId}
                          aria-label={`Skill ${fieldIndex + 1}`}
                          className="min-w-8 max-w-48 bg-transparent font-semibold outline-none disabled:opacity-60"
                          disabled={removed || fieldRemoved}
                          maxLength={10_000}
                          onChange={(event) =>
                            setSemanticValues((current) => ({
                              ...current,
                              [field.id]: event.target.value,
                            }))
                          }
                          size={Math.max(2, skillValue.length)}
                          value={skillValue}
                        />
                        <span className="sr-only" id={chipSourceId}>
                          {field.anchors[0]
                            ? `Source page ${field.anchors[0].page}, characters ${field.anchors[0].start} to ${field.anchors[0].end}.`
                            : "User-added skill; no source anchor is claimed."}
                        </span>
                        {field.reviewState === "unreviewed" &&
                          !fieldRemoved && (
                            <button
                              aria-label={
                                confirmed
                                  ? `Unconfirm ${skillValue || "skill"}`
                                  : `Confirm ${skillValue || "skill"}`
                              }
                              aria-pressed={confirmed}
                              className={cn(
                                "grid size-5 place-items-center rounded-full border transition-colors",
                                confirmed
                                  ? "border-primary bg-primary text-white"
                                  : "border-line text-muted hover:border-primary hover:text-primary",
                              )}
                              disabled={removed}
                              onClick={() =>
                                setConfirmedFields((current) => ({
                                  ...current,
                                  [field.id]: !confirmed,
                                }))
                              }
                              type="button"
                            >
                              <Check aria-hidden="true" className="size-3" />
                            </button>
                          )}
                        <button
                          aria-label={
                            fieldRemoved
                              ? `Restore ${skillValue || "skill"}`
                              : `Remove ${skillValue || "skill"}`
                          }
                          className="grid size-5 place-items-center rounded-full text-muted transition-colors hover:bg-danger-soft hover:text-danger disabled:opacity-40"
                          disabled={removed}
                          onClick={() =>
                            setRemovedFields((current) => ({
                              ...current,
                              [field.id]: !fieldRemoved,
                            }))
                          }
                          type="button"
                        >
                          <X aria-hidden="true" className="size-3.5" />
                        </button>
                      </span>
                    );
                  })}
                </div>
              ) : (
                <div className="divide-y divide-line">
                  {entity.fields.map((field, fieldIndex) => {
                    const presentation = confidence(field.confidence);
                    const inputId = `semantic-${entityIndex}-${fieldIndex}`;
                    const sourceId = `${inputId}-source`;
                    const fieldRemoved = removedFields[field.id] ?? false;
                    const mappedName = fieldNames[field.id] ?? field.name;
                    return (
                      <div
                        className={
                          fieldRemoved
                            ? "grid gap-5 p-5 opacity-60 lg:grid-cols-2"
                            : "grid gap-5 p-5 lg:grid-cols-2"
                        }
                        key={field.id}
                      >
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-sm font-extrabold capitalize text-foreground">
                              {mappedName.replaceAll("_", " ")}
                            </h3>
                            <Badge tone={presentation.tone}>
                              {presentation.label}
                            </Badge>
                            <Badge
                              tone={
                                field.reviewState === "unreviewed"
                                  ? "warning"
                                  : field.reviewState === "removed"
                                    ? "danger"
                                    : "success"
                              }
                            >
                              {field.reviewState.replaceAll("_", " ")}
                            </Badge>
                          </div>
                          <blockquote
                            className="mt-3 whitespace-pre-wrap rounded-xl border border-line bg-surface-subtle p-3 text-sm leading-6 text-muted"
                            id={sourceId}
                          >
                            {field.anchors[0]?.excerpt ||
                              "User-added value; no source anchor is claimed."}
                          </blockquote>
                          {field.anchors[0] && (
                            <p className="mt-2 text-xs leading-5 text-muted">
                              Exact source anchor: page {field.anchors[0].page},
                              characters {field.anchors[0].start}–
                              {field.anchors[0].end}
                            </p>
                          )}
                        </div>
                        <div>
                          {nextKind !== entity.kind && (
                            <label className="block text-xs font-bold text-muted">
                              Fact classification
                              <select
                                className="mt-1 block rounded-lg border border-line bg-surface px-2 py-1.5 text-foreground"
                                disabled={removed || fieldRemoved}
                                onChange={(event) =>
                                  setFieldNames((current) => ({
                                    ...current,
                                    [field.id]: event.target.value,
                                  }))
                                }
                                value={mappedName}
                              >
                                {semanticFieldNamesForType(
                                  nextKind,
                                  field.fieldType,
                                ).map((candidate) => (
                                  <option key={candidate} value={candidate}>
                                    {candidate.replaceAll("_", " ")}
                                  </option>
                                ))}
                              </select>
                            </label>
                          )}
                          <label
                            className={
                              nextKind !== entity.kind
                                ? "mt-3 block text-sm font-extrabold capitalize text-foreground"
                                : "block text-sm font-extrabold capitalize text-foreground"
                            }
                            htmlFor={inputId}
                          >
                            Reviewed {mappedName.replaceAll("_", " ")}
                          </label>
                          <textarea
                            aria-describedby={sourceId}
                            className="mt-3 min-h-24 w-full resize-y rounded-xl border border-line bg-surface px-3 py-2.5 text-sm leading-6 text-foreground shadow-sm outline-none transition focus:border-primary focus:ring-3 focus:ring-primary/15"
                            disabled={removed || fieldRemoved}
                            id={inputId}
                            maxLength={10_000}
                            onChange={(event) =>
                              setSemanticValues((current) => ({
                                ...current,
                                [field.id]: event.target.value,
                              }))
                            }
                            value={semanticValues[field.id] ?? ""}
                          />
                          {field.fieldType === "date" && (
                            <label className="mt-2 block text-xs font-bold text-muted">
                              Date precision
                              <select
                                className="ml-2 rounded-lg border border-line bg-surface px-2 py-1.5 text-foreground"
                                onChange={(event) =>
                                  setDatePrecisions((current) => ({
                                    ...current,
                                    [field.id]: event.target
                                      .value as DatePrecision,
                                  }))
                                }
                                value={
                                  datePrecisions[field.id] ??
                                  field.datePrecision ??
                                  "unknown"
                                }
                              >
                                <option value="day">day</option>
                                <option value="month">month</option>
                                <option value="year">year</option>
                                <option value="unknown">unknown</option>
                              </select>
                            </label>
                          )}
                          <div className="mt-3 flex flex-wrap gap-3">
                            {field.reviewState === "unreviewed" && (
                              <label className="flex items-center gap-2 text-xs font-bold text-foreground">
                                <input
                                  checked={confirmedFields[field.id] ?? false}
                                  disabled={removed || fieldRemoved}
                                  onChange={(event) =>
                                    setConfirmedFields((current) => ({
                                      ...current,
                                      [field.id]: event.target.checked,
                                    }))
                                  }
                                  type="checkbox"
                                />
                                Confirm extracted value
                              </label>
                            )}
                            <Button
                              disabled={removed}
                              onClick={() =>
                                setRemovedFields((current) => ({
                                  ...current,
                                  [field.id]: !fieldRemoved,
                                }))
                              }
                              type="button"
                              variant="secondary"
                            >
                              <Trash2 aria-hidden="true" className="size-4" />
                              {fieldRemoved ? "Undo remove" : "Remove fact"}
                            </Button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
              {!removed && (
                <SemanticAddFieldForm
                  entity={{ ...entity, kind: nextKind }}
                  key={nextKind}
                  onAdd={(operation) =>
                    setAddedOperations((current) => [...current, operation])
                  }
                />
              )}
            </Card>
          );
        })
      )}
      <SemanticAddEntityForm
        onAdd={(operation) =>
          setAddedOperations((current) => [...current, operation])
        }
      />
      {addedOperations.length > 0 && (
        <Alert title="Pending user-added records" tone="info">
          {addedOperations.length} typed addition
          {addedOperations.length === 1 ? "" : "s"} will be recorded without
          claiming a source anchor.
          <Button
            className="mt-3"
            onClick={() => setAddedOperations([])}
            type="button"
            variant="secondary"
          >
            Clear pending additions
          </Button>
        </Alert>
      )}
    </div>
  );

  const structuredPanel =
    canonical.semanticSchemaVersion !== null
      ? semanticStructuredPanel
      : legacyStructuredPanel;

  const plainTextPanel = (
    <div className="py-5">
      <Card className="p-5">
        <h2 className="text-sm font-extrabold">Extracted plain text</h2>
        <p className="mt-1 text-xs leading-5 text-muted">
          This is text output, not an executable or visual document preview.
          {plainText?.truncated
            ? " The displayed output was safely truncated."
            : ""}
        </p>
        <pre className="mt-4 max-h-[36rem] overflow-auto whitespace-pre-wrap rounded-xl bg-slate-950 p-4 text-xs leading-6 text-slate-100">
          {plainText?.text || "No plain text was extracted."}
        </pre>
      </Card>
    </div>
  );

  const readingOrderPanel = (
    <div className="py-5">
      <Card className="p-5">
        <h2 className="text-sm font-extrabold">Detected reading order</h2>
        {readingOrder && readingOrder.blocks.length > 0 ? (
          <ol className="mt-4 space-y-3">
            {readingOrder.blocks.map((block) => (
              <li
                className="flex gap-3 rounded-xl border border-line p-3 text-sm leading-6"
                key={`${block.index}-${block.page ?? "none"}`}
              >
                <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-primary-soft text-xs font-black text-primary">
                  {block.index + 1}
                </span>
                <span className="whitespace-pre-wrap text-muted">
                  {block.text}
                </span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="mt-4 text-sm text-muted">
            No reading-order blocks were available.
          </p>
        )}
      </Card>
    </div>
  );

  return (
    <main
      className={
        access === "account"
          ? "mx-auto max-w-6xl p-4 sm:p-6 lg:p-8"
          : "site-container py-8 sm:py-12"
      }
      id="main-content"
    >
      <header className="mb-6">
        <p className="eyebrow">Parse review</p>
        <h1 className="mt-2 text-2xl font-black tracking-[-0.035em] text-foreground sm:text-3xl">
          Review what Rezumi extracted
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
          Check uncertain fields from {document.displayFilename}. Saving creates
          a reviewed canonical version; it never edits or overwrites the
          uploaded source.
        </p>
      </header>

      {canonical.warnings.length > 0 && (
        <Alert
          className="mb-5"
          title="Parser warnings need review"
          tone="warning"
        >
          <ul className="list-disc space-y-1 pl-5">
            {canonical.warnings.map((warning) => (
              <li key={`${warning.code}-${warning.fieldId ?? "general"}`}>
                {warning.message}
              </li>
            ))}
          </ul>
        </Alert>
      )}
      {canonical.semanticWarnings.length > 0 && (
        <Alert
          className="mb-5"
          title="Typed fields need attention"
          tone="warning"
        >
          <ul className="list-disc space-y-1 pl-5">
            {canonical.semanticWarnings.map((warning) => (
              <li key={`${warning.code}-${warning.fieldId ?? "semantic"}`}>
                {warning.message}
              </li>
            ))}
          </ul>
        </Alert>
      )}
      {canonical.legacyUpgradeRequired && (
        <Alert
          className="mb-5"
          title="Legacy parse will be upgraded"
          tone="info"
        >
          This older snapshot does not yet contain typed semantic records.
          Recording a correction or confirming no changes creates an immutable
          versioned semantic successor; the original extraction remains
          available.
        </Alert>
      )}
      {failure && (
        <Alert className="mb-5" title="Review not saved" tone="danger">
          {failure}
          {conflict && (
            <Button
              className="mt-3"
              onClick={() => void load()}
              variant="secondary"
            >
              <RefreshCcw aria-hidden="true" className="size-4" /> Reload latest
              version
            </Button>
          )}
        </Alert>
      )}

      <Tabs
        label="Parsed resume views"
        tabs={[
          {
            id: "structured",
            label: "Structured fields",
            panel: structuredPanel,
          },
          { id: "plain", label: "Plain text", panel: plainTextPanel },
          {
            id: "reading-order",
            label: "Reading order",
            panel: readingOrderPanel,
          },
        ]}
      />

      <div
        aria-label="Explicit review required"
        className="sticky bottom-3 z-20 mt-5 flex flex-wrap items-center gap-3 rounded-[var(--radius-card)] border border-primary/30 bg-primary-soft px-4 py-3 shadow-[var(--shadow-md)]"
        role="group"
      >
        <label className="flex min-w-0 flex-1 items-start gap-2 text-xs font-bold text-foreground">
          <input
            checked={confirmNoChanges}
            className="mt-0.5 shrink-0"
            onChange={(event) => setConfirmNoChanges(event.target.checked)}
            type="checkbox"
          />
          <span>
            I reviewed the extracted content and confirm that no changes are
            needed.
          </span>
        </label>
        <Button
          loading={saving}
          loadingLabel="Saving review…"
          onClick={() => void saveAndAnalyze()}
        >
          <FileCheck2 aria-hidden="true" className="size-4" />
          {fields.length > 0
            ? "Save review and analyze"
            : "Acknowledge and analyze"}
        </Button>
      </div>
    </main>
  );
}
