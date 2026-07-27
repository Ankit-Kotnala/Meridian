"use client";

import { Database, FileArchive, Trash2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Alert, Badge, Card, ErrorState, LoadingSkeleton } from "@careeros/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  getSettingsCapabilities,
  type SettingsCapabilities,
} from "../api/settings-api";

export function PrivacySettings() {
  const [capabilities, setCapabilities] = useState<SettingsCapabilities>();
  const [failure, setFailure] = useState<string>();

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
  }, [load]);

  if (!capabilities && !failure) return <LoadingSkeleton variant="form" />;
  if (!capabilities)
    return (
      <ErrorState
        description={failure ?? "We couldn’t load privacy capabilities."}
        onRetry={load}
        title="Privacy settings unavailable"
      />
    );

  return (
    <div className="space-y-5">
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
                <Badge tone="neutral">
                  {capabilities.accountExportAvailable
                    ? "Backend available"
                    : "Not configured"}
                </Badge>
              </div>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">
                A complete portable export must cover relational records,
                private objects, provenance, and audit-safe metadata.
              </p>
            </div>
          </div>
        </div>
        {!capabilities.accountExportAvailable && (
          <Alert className="mt-5" title="Export is unavailable" tone="warning">
            No account-export provider or complete inventory workflow is
            configured. CareerOS will not pretend that a partial download is a
            complete export.
          </Alert>
        )}
        {capabilities.accountExportAvailable && (
          <Alert className="mt-5" title="Export request path pending">
            This environment reports account-export support, but this settings
            page does not yet expose the complete, audited request workflow. No
            partial download is presented as a complete export.
          </Alert>
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
                <Badge tone="neutral">
                  {capabilities.accountDeletionAvailable
                    ? "Available"
                    : "Not configured"}
                </Badge>
              </div>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">
                Account deletion must coordinate PostgreSQL, object storage,
                caches, queued work, providers, exports, and documented backup
                lifecycle behavior.
              </p>
            </div>
          </div>
        </div>
        {!capabilities.accountDeletionAvailable && (
          <Alert
            className="mt-5"
            title="Deletion is unavailable"
            tone="warning"
          >
            The complete account-erasure workflow and retention policy are not
            configured. Individual resume documents can still be deleted from
            Resume Health.
          </Alert>
        )}
        {capabilities.accountDeletionAvailable && (
          <Alert
            className="mt-5"
            title="Deletion capability reported"
            tone="info"
          >
            The server reports deletion support, but this settings view does not
            expose an unverified action path. Use only a complete, audited
            deletion workflow.
          </Alert>
        )}
      </Card>
    </div>
  );
}
