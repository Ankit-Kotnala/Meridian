"use client";

import { FileCheck2, RefreshCcw, ShieldQuestion } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  Tabs,
} from "@careeros/ui";

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
} from "../api/types";

function confidence(value: number) {
  if (value >= 85)
    return { label: `High confidence, ${value}%`, tone: "success" as const };
  if (value >= 60)
    return { label: `Review recommended, ${value}%`, tone: "warning" as const };
  return { label: `Low confidence, ${value}%`, tone: "danger" as const };
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
      if (changedFields.length > 0) {
        const reviewed = await updateCanonicalResume(
          access,
          documentId,
          canonical.version,
          {
            fields: changedFields,
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

  const structuredPanel = (
    <div className="space-y-5 py-5">
      {canonical.sections.length === 0 ? (
        <EmptyState
          description="CareerOS could not identify reliable structured sections. Review the plain text and try a cleaner source document."
          title="No structured sections found"
        />
      ) : (
        canonical.sections.map((section, sectionIndex) => (
          <Card className="overflow-hidden" key={section.id}>
            <header className="border-b border-line bg-slate-50 px-5 py-4">
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
                        className="mt-3 whitespace-pre-wrap rounded-xl border border-line bg-slate-50 p-3 text-sm leading-6 text-muted"
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
                        className="mt-3 min-h-32 w-full resize-y rounded-xl border border-line bg-white px-3 py-2.5 text-sm leading-6 text-foreground shadow-sm outline-none transition focus:border-primary focus:ring-3 focus:ring-primary/15"
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
          Review what CareerOS extracted
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

      <Card className="sticky bottom-3 mt-5 flex flex-col gap-4 p-4 shadow-xl sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <ShieldQuestion
            aria-hidden="true"
            className="mt-0.5 size-5 shrink-0 text-primary"
          />
          <div>
            <p className="text-sm font-extrabold">Explicit review required</p>
            <p className="mt-1 text-xs leading-5 text-muted">
              {fields.length > 0
                ? "Confirming these values starts a new deterministic analysis from this reviewed snapshot."
                : "Acknowledge that no reliable text was extracted. The report will show insufficient data instead of inventing a score."}
            </p>
          </div>
        </div>
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
      </Card>
    </main>
  );
}
