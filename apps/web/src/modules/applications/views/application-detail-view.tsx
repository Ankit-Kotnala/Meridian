"use client";

import { ArrowLeft, RefreshCcw, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Badge,
  Button,
  ConfirmDialog,
  ErrorState,
  LoadingSkeleton,
  PageHeader,
  Tabs,
  buttonStyles,
} from "@careeros/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  ApiRequestError,
  deleteApplication,
  getApplication,
  updateApplicationStage,
} from "../api/applications-api";
import type { ApplicationDetail, ApplicationStage } from "../api/types";
import { ApplicationActivityPanel } from "../components/application-activity-panel";
import {
  formatDate,
  humanize,
  stageTone,
} from "../components/application-options";
import { ApplicationOverviewPanel } from "../components/application-overview-panel";
import { ApplicationPacksPanel } from "../components/application-packs-panel";
import { ApplicationStageControl } from "../components/application-stage-control";

type DetailTabId = "overview" | "activity" | "packs";

export function ApplicationDetailView({
  applicationId,
}: {
  applicationId: string;
}) {
  const router = useRouter();
  const [application, setApplication] = useState<ApplicationDetail>();
  const [failure, setFailure] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const [conflict, setConflict] = useState(false);
  const [busyKey, setBusyKey] = useState<string>();
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<DetailTabId>("overview");
  const [mountedTabs, setMountedTabs] = useState<ReadonlySet<DetailTabId>>(
    () => new Set(["overview"]),
  );
  const [reloadEpoch, setReloadEpoch] = useState(0);

  const load = useCallback(
    async (resetMountedPanels = false) => {
      setFailure(undefined);
      setConflict(false);
      try {
        const current = await getApplication(applicationId);
        setApplication(current);
        if (resetMountedPanels) {
          setReloadEpoch((epoch) => epoch + 1);
        }
      } catch (error) {
        setFailure(
          requestErrorMessage(error, "The application could not be loaded."),
        );
      }
    },
    [applicationId],
  );

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  function reportFailure(message: string, stale: boolean) {
    setSuccess(undefined);
    setFailure(message);
    setConflict(stale);
  }

  function reportSuccess(message: string) {
    setFailure(undefined);
    setConflict(false);
    setSuccess(message);
  }

  function selectTab(tabId: string) {
    if (tabId !== "overview" && tabId !== "activity" && tabId !== "packs") {
      return;
    }
    setActiveTab(tabId);
    setMountedTabs((current) =>
      current.has(tabId) ? current : new Set([...current, tabId]),
    );
  }

  function changeOpenTaskCount(delta: number) {
    setApplication((current) =>
      current
        ? {
            ...current,
            openTaskCount: Math.max(0, current.openTaskCount + delta),
          }
        : current,
    );
  }

  function changePackCount(delta: number) {
    setApplication((current) =>
      current
        ? {
            ...current,
            packCount: Math.max(0, current.packCount + delta),
          }
        : current,
    );
  }

  async function moveStage(
    current: ApplicationDetail,
    stage: ApplicationStage,
    reopenReason?: string,
  ) {
    setBusyKey("stage");
    setFailure(undefined);
    setSuccess(undefined);
    setConflict(false);
    try {
      const updated = await updateApplicationStage(current, {
        ...(reopenReason ? { reopenReason } : {}),
        stage,
      });
      setApplication(updated);
      reportSuccess(`Application moved to ${humanize(updated.stage)}.`);
    } catch (error) {
      const stale =
        error instanceof ApiRequestError &&
        (error.failure.status === 409 || error.failure.status === 412);
      reportFailure(
        stale
          ? "This application changed in another session. Reload before moving it."
          : requestErrorMessage(error, "The stage could not be updated."),
        stale,
      );
    } finally {
      setBusyKey(undefined);
    }
  }

  async function remove() {
    if (!application) return;
    setBusyKey("delete");
    try {
      await deleteApplication(application);
      router.replace("/applications");
      router.refresh();
    } catch (error) {
      const stale =
        error instanceof ApiRequestError &&
        (error.failure.status === 409 || error.failure.status === 412);
      setDeleteOpen(false);
      reportFailure(
        stale
          ? "This application changed in another session. Reload before deleting it."
          : requestErrorMessage(error, "The application could not be deleted."),
        stale,
      );
    } finally {
      setBusyKey(undefined);
    }
  }

  if (!application && failure) {
    return (
      <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
        <ErrorState
          description={failure}
          onRetry={() => void load()}
          title="Application unavailable"
        />
      </main>
    );
  }

  if (!application) {
    return <ApplicationDetailLoading />;
  }

  return (
    <main
      className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8"
      id="main-content"
    >
      <Link
        className={`${buttonStyles.base} ${buttonStyles.ghost} -ml-3`}
        href="/applications"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        All applications
      </Link>

      <section
        aria-labelledby="application-title"
        className="rounded-card border border-border bg-surface-raised p-4 sm:p-5"
      >
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={stageTone(application.stage)}>
                {humanize(application.stage)}
              </Badge>
              <Badge tone="neutral">
                Referral: {humanize(application.referralStatus)}
              </Badge>
              {application.outcomeStatus !== "none" && (
                <Badge
                  tone={
                    application.outcomeStatus === "offer"
                      ? "success"
                      : "neutral"
                  }
                >
                  Outcome: {humanize(application.outcomeStatus)}
                </Badge>
              )}
            </div>
            <PageHeader
              className="mt-3"
              description={
                [application.company, application.location]
                  .filter(Boolean)
                  .join(" · ") || "Company and location not recorded"
              }
              id="application-title"
              title={application.jobTitle}
            />
            <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-sm">
              <div>
                <dt className="inline font-bold text-muted">Deadline: </dt>
                <dd className="inline text-foreground">
                  {formatDate(application.applicationDeadline)}
                </dd>
              </div>
              <div>
                <dt className="inline font-bold text-muted">Follow-up: </dt>
                <dd className="inline text-foreground">
                  {formatDate(application.followUpAt)}
                </dd>
              </div>
              <div>
                <dt className="inline font-bold text-muted">Source: </dt>
                <dd className="inline text-foreground">
                  {application.source || "Not recorded"}
                </dd>
              </div>
              <div>
                <dt className="inline font-bold text-muted">Industry: </dt>
                <dd className="inline text-foreground">
                  {application.industry || "Not recorded"}
                </dd>
              </div>
            </dl>
          </div>
          <div className="w-full max-w-sm">
            <ApplicationStageControl
              application={application}
              busy={busyKey === "stage"}
              key={`stage-control-${reloadEpoch}`}
              onMove={(current, stage, reopenReason) =>
                void moveStage(
                  current as ApplicationDetail,
                  stage,
                  reopenReason,
                )
              }
            />
          </div>
        </div>
      </section>

      {failure && (
        <Alert
          title={conflict ? "Reload required" : "Action failed"}
          tone="danger"
        >
          <p>{failure}</p>
          {conflict && (
            <Button
              className="mt-3 min-h-9 px-3"
              onClick={() => void load(true)}
            >
              <RefreshCcw aria-hidden="true" className="size-4" />
              Reload current data
            </Button>
          )}
        </Alert>
      )}
      {success && (
        <Alert title="Application updated" tone="success">
          {success}
        </Alert>
      )}

      <Tabs
        label="Application details"
        onValueChange={selectTab}
        tabs={[
          {
            id: "overview",
            label: "Overview",
            panel: (
              <div className="pt-5">
                <ApplicationOverviewPanel
                  application={application}
                  key={`overview-reload-${reloadEpoch}`}
                  onChange={setApplication}
                  onFailure={reportFailure}
                  onSuccess={reportSuccess}
                />
              </div>
            ),
          },
          {
            id: "activity",
            label: `Tasks, notes & timeline (${application.openTaskCount})`,
            panel: mountedTabs.has("activity") ? (
              <div className="pt-5">
                <ApplicationActivityPanel
                  application={application}
                  onFailure={reportFailure}
                  onOpenTaskCountChange={changeOpenTaskCount}
                  onSuccess={reportSuccess}
                  reloadEpoch={reloadEpoch}
                />
              </div>
            ) : null,
          },
          {
            id: "packs",
            label: `Application packs (${application.packCount})`,
            panel: mountedTabs.has("packs") ? (
              <div className="pt-5">
                <ApplicationPacksPanel
                  application={application}
                  onFailure={reportFailure}
                  onPackCountChange={changePackCount}
                  onSuccess={reportSuccess}
                  reloadEpoch={reloadEpoch}
                />
              </div>
            ) : null,
          },
        ]}
        value={activeTab}
      />

      <section className="rounded-card border border-danger bg-surface-raised p-4 sm:p-5">
        <h2 className="text-lg font-black text-foreground">
          Delete application
        </h2>
        <p className="mt-2 text-sm text-muted">
          Delete this tracker record and its application-only tasks, notes,
          events, and generated documents. The original saved job, resume, and
          evidence records remain unchanged.
        </p>
        <Button
          className="mt-4"
          onClick={() => setDeleteOpen(true)}
          variant="danger"
        >
          <Trash2 aria-hidden="true" className="size-4" />
          Delete application
        </Button>
      </section>

      <ConfirmDialog
        confirmLabel="Delete application"
        description={
          <>
            Delete the application tracker for{" "}
            <strong>{application.jobTitle}</strong>? This application record
            cannot be restored from the workspace.
          </>
        }
        loading={busyKey === "delete"}
        onConfirm={() => void remove()}
        onOpenChange={setDeleteOpen}
        open={deleteOpen}
        title="Delete this application?"
      />
    </main>
  );
}

export function ApplicationDetailLoading() {
  return (
    <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
      <LoadingSkeleton variant="page" />
    </main>
  );
}

export function ApplicationDetailRouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
      <ErrorState
        description={error.message || "Refresh and try again."}
        onRetry={reset}
        title="Application unavailable"
      />
    </main>
  );
}
