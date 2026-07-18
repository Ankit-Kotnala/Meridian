"use client";

import {
  ArrowLeft,
  Archive,
  Download,
  Pencil,
  RefreshCcw,
  ShieldAlert,
  Trash2,
  Upload,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  FieldLabel,
  FileUploadField,
  LoadingSkeleton,
  Progress,
  Select,
  formatBytes,
} from "@careeros/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  ApiRequestError,
  archiveEvidence,
  confirmEvidence,
  createAttachmentUploadIntent,
  deleteAttachment,
  deleteEvidence,
  finalizeAttachmentUpload,
  getAttachmentDownloadUrl,
  getEvidenceItem,
  markEvidenceUnsupported,
  resolveEvidenceConflict,
  restoreEvidence,
  uploadAttachment,
  updateEvidence,
} from "../api/career-vault-api";
import type { EvidenceClaimUpdate, EvidenceItem } from "../api/types";
import { EvidenceEditForm } from "../components/evidence-edit-form";
import {
  EvidenceEligibility,
  EvidenceStateBadge,
  ProvenanceList,
} from "../components/evidence-semantics";
import { FieldErrorSummary } from "../components/form-controls";
import {
  type FieldErrors,
  validateEvidenceUpdate,
} from "../validation/career-vault-validation";

function readable(value: string): string {
  return value.replaceAll("_", " ");
}

function date(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(
    new Date(value),
  );
}

export function EvidenceDetailView({ evidenceId }: { evidenceId: string }) {
  const router = useRouter();
  const [evidence, setEvidence] = useState<EvidenceItem>();
  const [failure, setFailure] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [pendingAttachmentDelete, setPendingAttachmentDelete] =
    useState<string>();
  const [file, setFile] = useState<File>();
  const [fileError, setFileError] = useState<string>();
  const [uploadProgress, setUploadProgress] = useState<number | null>();
  const errorRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    setFailure(undefined);
    try {
      setEvidence(await getEvidenceItem(evidenceId));
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "We couldn’t load this evidence item."),
      );
    }
  }, [evidenceId]);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  async function transition(
    action: (item: EvidenceItem) => Promise<EvidenceItem>,
    message: string,
  ) {
    if (!evidence) return;
    setLoading(true);
    setFailure(undefined);
    setNotice(undefined);
    try {
      setEvidence(await action(evidence));
      setNotice(message);
    } catch (error) {
      setFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This evidence changed or the requested transition is no longer allowed. Reload the current state."
          : requestErrorMessage(
              error,
              "We couldn’t change this evidence item.",
            ),
      );
    } finally {
      setLoading(false);
    }
  }

  async function removeEvidence() {
    if (!evidence) return;
    setLoading(true);
    setFailure(undefined);
    try {
      await deleteEvidence(evidence);
      router.push("/evidence");
      router.refresh();
    } catch (error) {
      setFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This evidence is still in use or changed in another tab. Review its usage before deleting."
          : requestErrorMessage(
              error,
              "We couldn’t delete this evidence item.",
            ),
      );
      setConfirmDelete(false);
    } finally {
      setLoading(false);
    }
  }

  async function saveEvidence(input: EvidenceClaimUpdate) {
    if (!evidence) return;
    const nextErrors = validateEvidenceUpdate(input);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      queueMicrotask(() => errorRef.current?.focus());
      return;
    }
    setLoading(true);
    setFailure(undefined);
    setNotice(undefined);
    try {
      setEvidence(await updateEvidence(evidence, input));
      setEditing(false);
      setErrors({});
      setNotice(
        "Evidence saved as a new material revision. Provenance and links were preserved.",
      );
    } catch (error) {
      setFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This evidence changed in another tab. Reload before saving."
          : requestErrorMessage(error, "We couldn’t save this evidence item."),
      );
    } finally {
      setLoading(false);
    }
  }

  function chooseFile(next: File | undefined) {
    setFileError(undefined);
    if (!next) {
      setFile(undefined);
      return;
    }
    const allowed = new Set([
      "application/pdf",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]);
    if (!allowed.has(next.type)) {
      setFileError(
        "Choose a PDF or DOCX file. The server also verifies its signature.",
      );
      return;
    }
    if (next.size < 1) {
      setFileError("The selected file is empty.");
      return;
    }
    setFile(next);
  }

  async function attach() {
    if (!evidence || !file) return;
    setLoading(true);
    setFailure(undefined);
    setNotice(undefined);
    setUploadProgress(null);
    const controller = new AbortController();
    try {
      const intent = await createAttachmentUploadIntent(evidence, file);
      await uploadAttachment(
        intent,
        file,
        setUploadProgress,
        controller.signal,
      );
      setEvidence(await finalizeAttachmentUpload(evidence, intent));
      setFile(undefined);
      setUploadProgress(undefined);
      setNotice("Attachment uploaded and admitted for server-side scanning.");
    } catch (error) {
      setUploadProgress(undefined);
      setFailure(
        requestErrorMessage(error, "The attachment upload did not complete."),
      );
    } finally {
      setLoading(false);
    }
  }

  async function removeAttachment() {
    if (!evidence || !pendingAttachmentDelete) return;
    setLoading(true);
    setFailure(undefined);
    try {
      setEvidence(await deleteAttachment(evidence, pendingAttachmentDelete));
      setPendingAttachmentDelete(undefined);
      setNotice("Attachment deletion requested.");
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "We couldn’t delete this attachment."),
      );
    } finally {
      setLoading(false);
    }
  }

  async function downloadAttachment(attachmentId: string, filename: string) {
    if (!evidence) return;
    setLoading(true);
    setFailure(undefined);
    try {
      const url = await getAttachmentDownloadUrl(evidence.id, attachmentId);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.rel = "noopener noreferrer";
      anchor.target = "_blank";
      anchor.setAttribute("aria-label", `Download ${filename}`);
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      setNotice("A short-lived private download was opened.");
    } catch (error) {
      setFailure(
        requestErrorMessage(
          error,
          "We couldn’t prepare this private download.",
        ),
      );
    } finally {
      setLoading(false);
    }
  }

  if (!evidence && !failure) {
    return (
      <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
        <LoadingSkeleton />
      </main>
    );
  }
  if (!evidence) {
    return (
      <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
        <ErrorState
          description={failure ?? "This evidence item could not be loaded."}
          onRetry={load}
          title="Evidence unavailable"
        />
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
      <Link
        className="mb-5 inline-flex items-center gap-2 text-sm font-bold text-primary"
        href="/evidence"
      >
        <ArrowLeft aria-hidden="true" className="size-4" /> Back to Evidence
        Vault
      </Link>
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <EvidenceStateBadge state={evidence.state} />
            {evidence.lifecycle === "archived" && (
              <Badge tone="neutral">Archived</Badge>
            )}
          </div>
          <h1 className="mt-3 text-2xl font-black tracking-[-0.035em] sm:text-3xl">
            {evidence.title}
          </h1>
          <p className="mt-2 text-sm capitalize text-muted">
            {readable(evidence.type)} · revision {evidence.revision}
          </p>
        </div>
        <Button onClick={() => void load()} variant="secondary">
          <RefreshCcw aria-hidden="true" className="size-4" /> Reload
        </Button>
      </header>

      {failure && (
        <Alert className="mt-5" title="Evidence not changed" tone="danger">
          {failure}
        </Alert>
      )}
      {notice && (
        <Alert className="mt-5" title="Evidence updated" tone="success">
          {notice}
        </Alert>
      )}

      <div className="mt-6">
        <EvidenceEligibility evidence={evidence} />
      </div>
      {evidence.eligibilityReasons.length > 0 && (
        <Card className="mt-4 p-4">
          <h2 className="text-sm font-extrabold">
            Why eligibility is restricted
          </h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted">
            {evidence.eligibilityReasons.map((reason) => (
              <li key={reason}>{readable(reason)}</li>
            ))}
          </ul>
        </Card>
      )}

      <Card className="mt-5 p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h2 className="text-lg font-extrabold">Claim and actions</h2>
          <Button
            onClick={() => {
              setEditing((value) => !value);
              setErrors({});
            }}
            variant="secondary"
          >
            <Pencil aria-hidden="true" className="size-4" />{" "}
            {editing ? "Close editor" : "Edit evidence"}
          </Button>
        </div>
        {editing ? (
          <>
            <FieldErrorSummary errors={errors} ref={errorRef} />
            <EvidenceEditForm
              errors={errors}
              evidence={evidence}
              loading={loading}
              onCancel={() => setEditing(false)}
              onSubmit={(input) => void saveEvidence(input)}
            />
          </>
        ) : (
          <p className="mt-3 whitespace-pre-wrap text-sm leading-6">
            {evidence.description}
          </p>
        )}
        <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-3">
          <div>
            <dt className="font-bold text-muted">Organization or project</dt>
            <dd>{evidence.organizationOrProject || "Not added"}</dd>
          </div>
          <div>
            <dt className="font-bold text-muted">Period</dt>
            <dd>
              {evidence.startDate || "Not added"} –{" "}
              {evidence.endDate ||
                (evidence.startDate ? "Present" : "Not added")}
            </dd>
          </div>
          <div>
            <dt className="font-bold text-muted">Last updated</dt>
            <dd>{date(evidence.updatedAt)}</dd>
          </div>
        </dl>
        <div className="mt-5 flex flex-wrap gap-3">
          {evidence.lifecycle === "active" &&
            evidence.state !== "confirmed" &&
            evidence.state !== "verified" && (
              <Button
                loading={loading}
                onClick={() =>
                  void transition(
                    confirmEvidence,
                    "Evidence confirmed. Eligibility was recomputed by the server.",
                  )
                }
              >
                Confirm evidence
              </Button>
            )}
          {evidence.state !== "unsupported" && (
            <Button
              disabled={loading}
              onClick={() =>
                void transition(
                  markEvidenceUnsupported,
                  "Evidence marked unsupported.",
                )
              }
              variant="secondary"
            >
              <ShieldAlert aria-hidden="true" className="size-4" /> Mark
              unsupported
            </Button>
          )}
          {evidence.lifecycle === "active" ? (
            <Button
              disabled={loading}
              onClick={() =>
                void transition(archiveEvidence, "Evidence archived.")
              }
              variant="secondary"
            >
              <Archive aria-hidden="true" className="size-4" /> Archive
            </Button>
          ) : (
            <Button
              disabled={loading}
              onClick={() =>
                void transition(restoreEvidence, "Evidence restored.")
              }
              variant="secondary"
            >
              Restore
            </Button>
          )}
          <Button
            disabled={loading}
            onClick={() => setConfirmDelete(true)}
            variant="danger"
          >
            <Trash2 aria-hidden="true" className="size-4" /> Delete
          </Button>
        </div>
      </Card>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card className="p-5 sm:p-6">
          <h2 className="text-lg font-extrabold">Provenance</h2>
          <p className="mt-1 text-sm text-muted">
            Exact source snapshots and spans are preserved when available.
          </p>
          <div className="mt-4">
            <ProvenanceList values={evidence.provenance} />
          </div>
        </Card>
        <Card className="p-5 sm:p-6">
          <h2 className="text-lg font-extrabold">Structured metrics</h2>
          {evidence.metrics.length === 0 ? (
            <p className="mt-4 text-sm text-muted">
              No numeric claim is attached.
            </p>
          ) : (
            <dl className="mt-4 space-y-4">
              {evidence.metrics.map((metric) => (
                <div
                  className="rounded-xl border border-line p-4"
                  key={metric.id ?? `${metric.name}-${metric.periodStart}`}
                >
                  <dt className="font-extrabold">{metric.name}</dt>
                  <dd className="mt-1 text-sm">
                    {metric.value} {metric.unit}
                  </dd>
                  <dd className="mt-1 text-xs text-muted">
                    {metric.periodStart}
                    {metric.periodEnd ? ` – ${metric.periodEnd}` : ""} ·{" "}
                    {metric.precision} · {metric.attribution} attribution
                  </dd>
                  {metric.baseline && (
                    <dd className="mt-1 text-xs text-muted">
                      Baseline: {metric.baseline}
                      {metric.comparator ? ` (${metric.comparator})` : ""}
                    </dd>
                  )}
                </div>
              ))}
            </dl>
          )}
        </Card>
      </div>

      <Card className="mt-5 p-5 sm:p-6">
        <h2 className="text-lg font-extrabold">Private attachments</h2>
        <p className="mt-1 text-sm leading-6 text-muted">
          Only PDF and DOCX are admitted. Uploads remain private, are scanned
          fail-closed, and do not make a claim supported by themselves.
        </p>
        <div className="mt-5 grid gap-5 lg:grid-cols-2">
          <div>
            <FileUploadField
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              disabled={loading}
              error={fileError}
              hint="The server validates size, signature, and content before use."
              id="evidence-attachment"
              label="Add a supporting file"
              onFileChange={chooseFile}
              selectedFile={file}
            />
            {uploadProgress !== undefined && (
              <Progress
                className="mt-4"
                label="Uploading attachment"
                value={uploadProgress}
              />
            )}
            <Button
              className="mt-4"
              disabled={!file || loading}
              onClick={() => void attach()}
            >
              <Upload aria-hidden="true" className="size-4" /> Upload privately
            </Button>
          </div>
          {evidence.attachments.length === 0 ? (
            <EmptyState
              description="No private supporting files are connected to this evidence."
              title="No attachments"
            />
          ) : (
            <ul className="space-y-3">
              {evidence.attachments.map((attachment) => (
                <li
                  className="rounded-xl border border-line p-4"
                  key={attachment.id}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-extrabold">
                        {attachment.displayFilename}
                      </p>
                      <p className="mt-1 text-xs text-muted">
                        {formatBytes(attachment.sizeBytes)} ·{" "}
                        {attachment.status}
                      </p>
                      {attachment.safeErrorCode && (
                        <p className="mt-1 text-xs text-danger">
                          Processing issue: {readable(attachment.safeErrorCode)}
                        </p>
                      )}
                    </div>
                    <div className="flex gap-1">
                      {attachment.status === "ready" && (
                        <Button
                          aria-label={`Download ${attachment.displayFilename}`}
                          className="px-3"
                          disabled={loading}
                          onClick={() =>
                            void downloadAttachment(
                              attachment.id,
                              attachment.displayFilename,
                            )
                          }
                          variant="ghost"
                        >
                          <Download aria-hidden="true" className="size-4" />
                        </Button>
                      )}
                      <Button
                        aria-label={`Delete ${attachment.displayFilename}`}
                        className="px-3"
                        disabled={loading}
                        onClick={() =>
                          setPendingAttachmentDelete(attachment.id)
                        }
                        variant="ghost"
                      >
                        <Trash2 aria-hidden="true" className="size-4" />
                      </Button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>

      {evidence.conflicts.length > 0 && (
        <Card className="mt-5 p-5 sm:p-6">
          <h2 className="text-lg font-extrabold">Conflict review</h2>
          <p className="mt-1 text-sm text-muted">
            CareerOS never silently chooses between contradictory records.
          </p>
          <ul className="mt-4 space-y-4">
            {evidence.conflicts.map((conflict) => (
              <li
                className="rounded-xl border border-line p-4"
                key={conflict.id}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge
                    tone={conflict.status === "open" ? "warning" : "neutral"}
                  >
                    {conflict.status}
                  </Badge>
                  <p className="font-bold">{readable(conflict.code)}</p>
                </div>
                <p className="mt-2 text-sm text-muted">{conflict.message}</p>
                {conflict.status === "open" && (
                  <form
                    className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end"
                    onSubmit={(event) => {
                      event.preventDefault();
                      const form = new FormData(event.currentTarget);
                      void transition(
                        (item) =>
                          resolveEvidenceConflict(
                            item,
                            conflict.id,
                            String(form.get("resolution")) as
                              | "keep_both"
                              | "mark_unsupported"
                              | "prefer_current"
                              | "prefer_related",
                          ),
                        "Conflict resolution saved and eligibility recomputed.",
                      );
                    }}
                  >
                    <div className="flex-1 space-y-2">
                      <FieldLabel htmlFor={`resolution-${conflict.id}`}>
                        Resolution
                      </FieldLabel>
                      <Select
                        defaultValue="keep_both"
                        id={`resolution-${conflict.id}`}
                        name="resolution"
                      >
                        <option value="keep_both">
                          Keep both with conflict recorded
                        </option>
                        <option value="prefer_current">
                          Prefer this evidence
                        </option>
                        <option value="prefer_related">
                          Prefer the related evidence
                        </option>
                        <option value="mark_unsupported">
                          Mark this evidence unsupported
                        </option>
                      </Select>
                    </div>
                    <Button
                      disabled={loading}
                      type="submit"
                      variant="secondary"
                    >
                      Save resolution
                    </Button>
                  </form>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card className="p-5 sm:p-6">
          <h2 className="text-lg font-extrabold">Used by</h2>
          {evidence.usage.length === 0 ? (
            <p className="mt-3 text-sm text-muted">
              This evidence is not used by another record or output.
            </p>
          ) : (
            <ul className="mt-3 space-y-2">
              {evidence.usage.map((usage) => (
                <li className="text-sm" key={usage.id}>
                  <span className="font-bold">{usage.label}</span>{" "}
                  <span className="text-muted">({usage.type})</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card className="p-5 sm:p-6">
          <h2 className="text-lg font-extrabold">State history</h2>
          {evidence.history.length === 0 ? (
            <p className="mt-3 text-sm text-muted">
              No state transitions are recorded yet.
            </p>
          ) : (
            <ol className="mt-3 space-y-3">
              {evidence.history.map((event) => (
                <li
                  className="border-l-2 border-primary/30 pl-3 text-sm"
                  key={event.id}
                >
                  <p className="font-bold">
                    {event.fromState ? `${readable(event.fromState)} → ` : ""}
                    {readable(event.toState)}
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    {event.reason || "No reason recorded"} · {event.actorLabel}{" "}
                    · {date(event.createdAt)}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>

      <ConfirmDialog
        confirmLabel="Delete evidence"
        description="Deletion is blocked when the evidence is still used. This action never silently rewrites a career document."
        loading={loading}
        onConfirm={() => void removeEvidence()}
        onOpenChange={setConfirmDelete}
        open={confirmDelete}
        title="Permanently delete this evidence?"
      />
      <ConfirmDialog
        confirmLabel="Delete attachment"
        description="The private object and its processing records will be removed through the authorized deletion workflow."
        loading={loading}
        onConfirm={() => void removeAttachment()}
        onOpenChange={(open) => {
          if (!open && !loading) setPendingAttachmentDelete(undefined);
        }}
        open={Boolean(pendingAttachmentDelete)}
        title="Delete this attachment?"
      />
    </main>
  );
}
