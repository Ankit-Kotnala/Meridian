"use client";

import {
  Database,
  Download,
  FileArchive,
  RefreshCw,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  ConfirmDialog,
  ErrorState,
  LoadingSkeleton,
} from "@careeros/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  createAccountExportDownload,
  getSettingsCapabilities,
  requestAccountDeletion,
  requestAccountExport,
  waitForAccountOperation,
  type AccountExportDownload,
  type AccountOperation,
  type AccountOperationCreated,
  type SettingsCapabilities,
} from "../api/settings-api";

type TrackedOperation = {
  operation: AccountOperation;
  token: string;
};

type OperationBusy = "deletion" | "download" | "export" | undefined;

const activeStatuses = new Set<AccountOperation["status"]>([
  "queued",
  "running",
  "retryWait",
]);

export function PrivacySettings() {
  const [capabilities, setCapabilities] = useState<SettingsCapabilities>();
  const [failure, setFailure] = useState<string>();
  const [busy, setBusy] = useState<OperationBusy>();
  const [exportOperation, setExportOperation] = useState<TrackedOperation>();
  const [deletionOperation, setDeletionOperation] =
    useState<TrackedOperation>();
  const [download, setDownload] = useState<AccountExportDownload>();
  const [deletionDialogOpen, setDeletionDialogOpen] = useState(false);
  const exportIntentKey = useRef<string | undefined>(undefined);
  const deletionIntentKey = useRef<string | undefined>(undefined);
  const pollingController = useRef<AbortController | undefined>(undefined);

  const load = useCallback(async () => {
    try {
      setCapabilities(await getSettingsCapabilities());
      setFailure(undefined);
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "We couldn’t load privacy capabilities."),
      );
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void load());
    return () => pollingController.current?.abort();
  }, [load]);

  async function monitorOperation(
    created: AccountOperationCreated,
    update: (value: TrackedOperation) => void,
  ) {
    pollingController.current?.abort();
    const controller = new AbortController();
    pollingController.current = controller;
    const tracked = { operation: created, token: created.operationToken };
    update(tracked);
    try {
      const operation = await waitForAccountOperation(created, {
        onUpdate: (next) => update({ operation: next, token: tracked.token }),
        signal: controller.signal,
      });
      update({ operation, token: tracked.token });
    } finally {
      if (pollingController.current === controller) {
        pollingController.current = undefined;
      }
    }
  }

  async function startExport() {
    setBusy("export");
    setFailure(undefined);
    setDownload(undefined);
    exportIntentKey.current ??= `settings-export:${crypto.randomUUID()}`;
    try {
      const created = await requestAccountExport(exportIntentKey.current);
      exportIntentKey.current = undefined;
      await monitorOperation(created, setExportOperation);
    } catch (error) {
      if (!(error instanceof Error && error.name === "AbortError")) {
        setFailure(
          requestErrorMessage(
            error,
            "We couldn’t request the account export. Your existing data remains unchanged.",
          ),
        );
      }
    } finally {
      setBusy(undefined);
    }
  }

  async function startDeletion() {
    setBusy("deletion");
    setFailure(undefined);
    deletionIntentKey.current ??= `settings-deletion:${crypto.randomUUID()}`;
    try {
      const created = await requestAccountDeletion(deletionIntentKey.current);
      deletionIntentKey.current = undefined;
      setDeletionDialogOpen(false);
      await monitorOperation(created, setDeletionOperation);
    } catch (error) {
      if (!(error instanceof Error && error.name === "AbortError")) {
        setFailure(
          requestErrorMessage(
            error,
            "We couldn’t start account deletion. No deletion was reported as complete.",
          ),
        );
      }
    } finally {
      setBusy(undefined);
    }
  }

  async function refreshOperation(
    tracked: TrackedOperation,
    kind: Exclude<OperationBusy, "download" | undefined>,
    update: (value: TrackedOperation) => void,
  ) {
    setBusy(kind);
    setFailure(undefined);
    try {
      await monitorOperation(
        { ...tracked.operation, operationToken: tracked.token },
        update,
      );
    } catch (error) {
      if (!(error instanceof Error && error.name === "AbortError")) {
        setFailure(
          requestErrorMessage(
            error,
            "We couldn’t refresh this operation. Its durable server state was not changed.",
          ),
        );
      }
    } finally {
      setBusy(undefined);
    }
  }

  async function createDownload() {
    if (!exportOperation) return;
    setBusy("download");
    setFailure(undefined);
    try {
      setDownload(
        await createAccountExportDownload(
          exportOperation.operation.id,
          exportOperation.token,
        ),
      );
    } catch (error) {
      setFailure(
        requestErrorMessage(
          error,
          "We couldn’t create a download link. The private export was not exposed.",
        ),
      );
    } finally {
      setBusy(undefined);
    }
  }

  if (!capabilities && !failure) return <LoadingSkeleton variant="form" />;
  if (!capabilities)
    return (
      <ErrorState
        description={failure ?? "We couldn’t load privacy capabilities."}
        onRetry={load}
        title="Privacy settings unavailable"
      />
    );

  const liveStatus =
    deletionOperation?.operation.status ?? exportOperation?.operation.status;

  return (
    <div className="space-y-5">
      <div aria-live="polite" className="sr-only">
        {liveStatus
          ? `Account operation status: ${statusLabel(liveStatus)}.`
          : ""}
      </div>

      {failure && (
        <Alert title="Privacy action needs attention" tone="danger">
          {failure}
        </Alert>
      )}

      <Card className="p-5 sm:p-7">
        <div className="flex items-start gap-3">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary">
            <Database aria-hidden="true" className="size-5" />
          </span>
          <div>
            <h2 className="text-lg font-extrabold text-foreground">
              Retention and document control
            </h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">
              Guest resume files expire after{" "}
              {capabilities.guestResumeRetentionHours} hours. Account resume
              documents remain owner-managed until you delete them.
            </p>
            <Link
              className="text-link mt-4 inline-flex text-sm"
              href="/resume-health/account"
            >
              Review or delete account resume documents
            </Link>
          </div>
        </div>
      </Card>

      <Card className="p-5 sm:p-7">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-slate-100 text-muted">
              <FileArchive aria-hidden="true" className="size-5" />
            </span>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-extrabold text-foreground">
                  Account data export
                </h2>
                <Badge
                  tone={
                    capabilities.accountExportAvailable ? "success" : "neutral"
                  }
                >
                  {capabilities.accountExportAvailable
                    ? "Available"
                    : "Not configured"}
                </Badge>
              </div>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">
                Create a private, portable ZIP containing your classified
                account records, eligible files, provenance, and an integrity
                manifest. Authentication secrets, queue state, and object keys
                are excluded.
              </p>
            </div>
          </div>
          {capabilities.accountExportAvailable && (
            <Button
              disabled={
                Boolean(busy) ||
                Boolean(
                  exportOperation &&
                  activeStatuses.has(exportOperation.operation.status),
                )
              }
              loading={busy === "export" && !exportOperation}
              loadingLabel="Requesting export…"
              onClick={() => void startExport()}
              variant="secondary"
            >
              <FileArchive aria-hidden="true" className="size-4" />
              Request export
            </Button>
          )}
        </div>

        {!capabilities.accountExportAvailable && (
          <Alert className="mt-5" title="Export is unavailable" tone="warning">
            No complete account-export provider is configured. CareerOS will not
            present a partial download as a complete export.
          </Alert>
        )}

        {exportOperation && (
          <OperationPanel
            busy={busy}
            {...(download ? { download } : {})}
            onCreateDownload={() => void createDownload()}
            onRefresh={() =>
              void refreshOperation(
                exportOperation,
                "export",
                setExportOperation,
              )
            }
            tracked={exportOperation}
          />
        )}
      </Card>

      <Card className="p-5 sm:p-7">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-danger-soft text-danger">
              <Trash2 aria-hidden="true" className="size-5" />
            </span>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-extrabold text-foreground">
                  Delete account
                </h2>
                <Badge
                  tone={
                    capabilities.accountDeletionAvailable
                      ? "warning"
                      : "neutral"
                  }
                >
                  {capabilities.accountDeletionAvailable
                    ? "Available"
                    : "Not configured"}
                </Badge>
              </div>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">
                Starting deletion disables sign-in immediately, revokes active
                sessions, removes classified primary-store records and private
                objects through a durable worker, and retains only the minimum
                operation status needed to report the outcome.
              </p>
              <p className="mt-2 max-w-2xl text-xs leading-5 text-muted">
                Primary-store completion does not claim immediate removal from
                backups or legally retained third-party records. Those windows
                require the approved production retention policy.
              </p>
            </div>
          </div>
          {capabilities.accountDeletionAvailable &&
            deletionOperation?.operation.status !== "succeeded" && (
              <Button
                disabled={Boolean(busy)}
                onClick={() => setDeletionDialogOpen(true)}
                variant="danger"
              >
                <Trash2 aria-hidden="true" className="size-4" />
                Start deletion
              </Button>
            )}
        </div>

        {!capabilities.accountDeletionAvailable && (
          <Alert
            className="mt-5"
            title="Deletion is unavailable"
            tone="warning"
          >
            The complete account-erasure workflow is not configured. Individual
            resume documents can still be deleted from Resume Health.
          </Alert>
        )}

        {deletionOperation && (
          <OperationPanel
            busy={busy}
            onRefresh={() =>
              void refreshOperation(
                deletionOperation,
                "deletion",
                setDeletionOperation,
              )
            }
            tracked={deletionOperation}
          />
        )}
      </Card>

      <ConfirmDialog
        confirmLabel="Delete account"
        description={
          <div className="space-y-3">
            <p>
              Your account will be disabled and every browser session revoked as
              soon as the request is accepted. This cannot be undone after the
              durable deletion completes.
            </p>
            <p className="font-bold text-danger">
              Keep this page open to see the capability-protected final status.
            </p>
          </div>
        }
        loading={busy === "deletion"}
        onConfirm={() => void startDeletion()}
        onOpenChange={setDeletionDialogOpen}
        open={deletionDialogOpen}
        title="Delete your CareerOS account?"
      />
    </div>
  );
}

function OperationPanel({
  busy,
  download,
  onCreateDownload,
  onRefresh,
  tracked,
}: {
  busy: OperationBusy;
  download?: AccountExportDownload;
  onCreateDownload?: () => void;
  onRefresh: () => void;
  tracked: TrackedOperation;
}) {
  const { operation } = tracked;
  const active = activeStatuses.has(operation.status);
  const isExport = operation.kind === "export";

  return (
    <div className="mt-5 rounded-xl border border-line bg-surface-subtle p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-muted">
            {isExport ? "Export operation" : "Deletion operation"}
          </p>
          <p className="mt-1 font-mono text-xs text-muted" title={operation.id}>
            {operation.id}
          </p>
        </div>
        <Badge tone={statusTone(operation.status)}>
          {statusLabel(operation.status)}
        </Badge>
      </div>

      <Alert
        className="mt-4"
        title={operationTitle(operation)}
        tone={operationTone(operation.status)}
      >
        {operationDescription(operation)}
      </Alert>

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-xs font-bold uppercase tracking-wide text-muted">
            Attempts
          </dt>
          <dd className="mt-1 font-semibold text-foreground">
            {operation.attempts} of {operation.maxAttempts}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-bold uppercase tracking-wide text-muted">
            Updated
          </dt>
          <dd className="mt-1 font-semibold text-foreground">
            {formatDate(operation.updatedAt)}
          </dd>
        </div>
        {isExport && operation.artifactSizeBytes && (
          <div>
            <dt className="text-xs font-bold uppercase tracking-wide text-muted">
              Archive size
            </dt>
            <dd className="mt-1 font-semibold text-foreground">
              {formatBytes(operation.artifactSizeBytes)}
            </dd>
          </div>
        )}
      </dl>

      <div className="mt-4 flex flex-wrap gap-3">
        {active && (
          <Button
            loading={
              (operation.kind === "export" && busy === "export") ||
              (operation.kind === "deletion" && busy === "deletion")
            }
            loadingLabel="Checking status…"
            onClick={onRefresh}
            variant="secondary"
          >
            <RefreshCw aria-hidden="true" className="size-4" />
            Refresh status
          </Button>
        )}
        {isExport && operation.status === "succeeded" && onCreateDownload && (
          <Button
            loading={busy === "download"}
            loadingLabel="Creating secure link…"
            onClick={onCreateDownload}
          >
            <ShieldCheck aria-hidden="true" className="size-4" />
            Create download link
          </Button>
        )}
        {!isExport && operation.status === "succeeded" && (
          <Link
            className="text-link inline-flex min-h-11 items-center"
            href="/"
          >
            Return to CareerOS home
          </Link>
        )}
      </div>

      {download && (
        <Alert className="mt-4" title="Private download ready" tone="success">
          <p>
            This short-lived link expires in {download.expiresInSeconds}{" "}
            seconds.
          </p>
          <a
            className="text-link mt-2 inline-flex min-h-11 items-center gap-2 font-bold"
            href={download.downloadUrl}
            rel="noreferrer"
            target="_blank"
          >
            <Download aria-hidden="true" className="size-4" />
            Download account export
          </a>
        </Alert>
      )}
    </div>
  );
}

function statusLabel(status: AccountOperation["status"]) {
  return {
    blocked: "Blocked safely",
    deadLettered: "Needs support",
    expired: "Expired",
    queued: "Queued",
    retryWait: "Waiting to retry",
    running: "Processing",
    succeeded: "Completed",
  }[status];
}

function statusTone(
  status: AccountOperation["status"],
): "danger" | "neutral" | "primary" | "success" | "warning" {
  if (status === "succeeded") return "success";
  if (status === "blocked" || status === "deadLettered") return "danger";
  if (status === "expired" || status === "retryWait") return "warning";
  if (status === "queued" || status === "running") return "primary";
  return "neutral";
}

function operationTone(
  status: AccountOperation["status"],
): "danger" | "info" | "success" | "warning" {
  if (status === "succeeded") return "success";
  if (status === "blocked" || status === "deadLettered") return "danger";
  if (status === "expired" || status === "retryWait") return "warning";
  return "info";
}

function operationTitle(operation: AccountOperation) {
  if (operation.status === "succeeded") {
    return operation.kind === "export"
      ? "Account export completed"
      : "Primary account deletion completed";
  }
  if (operation.status === "blocked") return "Operation blocked safely";
  if (operation.status === "deadLettered") return "Operation needs support";
  if (operation.status === "expired") return "Export artifact expired";
  return operation.status === "retryWait"
    ? "A safe retry is scheduled"
    : "Durable operation in progress";
}

function operationDescription(operation: AccountOperation) {
  if (operation.status === "succeeded") {
    return operation.kind === "export"
      ? "The server completed the classified export and recorded its integrity metadata. Create a short-lived download link when you are ready."
      : "CareerOS removed the classified primary account data and private objects. Backup and provider retention follow separately approved policies.";
  }
  if (operation.status === "blocked") {
    if (
      operation.blockedReason === "organization_ownership_transfer_required"
    ) {
      return "Transfer ownership of every organization you solely own, then sign in and submit a new deletion request.";
    }
    if (operation.blockedReason === "billing_retention_review_required") {
      return "Billing retention requires provider and legal review. Your account was restored; sign in again after that obligation is resolved.";
    }
    return "A policy obligation prevented completion. Your account was restored; sign in again and contact support with the operation ID.";
  }
  if (operation.status === "deadLettered") {
    return "The bounded retry budget was exhausted without reporting completion. Contact support with the operation ID; do not submit repeated requests.";
  }
  if (operation.status === "expired") {
    return "The private export passed its retention window and its stored artifact was removed before metadata was redacted. Request a new export if needed.";
  }
  if (operation.status === "retryWait") {
    return "A dependency was unavailable. CareerOS kept the durable state and scheduled a bounded retry.";
  }
  return operation.kind === "deletion"
    ? "Your session has been revoked. Keep this page open while the capability-protected status updates."
    : "CareerOS is collecting only classified account data and eligible private files. You can keep this page open or refresh the status.";
}

function formatBytes(value: number) {
  if (value < 1_024) return `${value} bytes`;
  if (value < 1_048_576) return `${(value / 1_024).toFixed(1)} KB`;
  return `${(value / 1_048_576).toFixed(1)} MB`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
