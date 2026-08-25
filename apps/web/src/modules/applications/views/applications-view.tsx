"use client";

import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  LayoutDashboard,
  List,
  Plus,
  RefreshCcw,
  Search,
  Settings2,
} from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from "react";

import {
  Alert,
  Button,
  ErrorState,
  Input,
  LoadingSkeleton,
  PageHeader,
  Select,
  cn,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  ApiRequestError,
  getApplicationCalendar,
  listApplications,
  updateApplicationStage,
} from "../api/applications-api";
import type {
  Application,
  ApplicationCalendar,
  ApplicationSort,
  ApplicationStage,
  ApplicationViewMode,
  OutcomeStatus,
} from "../api/types";
import {
  ApplicationAgenda,
  ApplicationBoard,
  ApplicationCollectionEmpty,
  ApplicationTable,
} from "../components/application-collection";
import {
  applicationSorts,
  applicationStages,
  applicationViews,
  humanize,
  outcomeStatuses,
} from "../components/application-options";
import { ApplicationProfilePanel } from "../components/application-profile-panel";
import { CreateApplicationForm } from "../components/create-application-form";

function validView(value: string | null): ApplicationViewMode {
  return applicationViews.some((item) => item.value === value)
    ? (value as ApplicationViewMode)
    : "board";
}

function validStage(value: string | null): ApplicationStage | "" {
  return applicationStages.includes(value as ApplicationStage)
    ? (value as ApplicationStage)
    : "";
}

function validSort(value: string | null): ApplicationSort {
  return applicationSorts.some((item) => item.value === value)
    ? (value as ApplicationSort)
    : "updated_desc";
}

function validOutcome(value: string | null): OutcomeStatus | "" {
  return outcomeStatuses.includes(value as OutcomeStatus)
    ? (value as OutcomeStatus)
    : "";
}

function currentMonth(): string {
  return new Date().toISOString().slice(0, 7);
}

function validMonth(value: string | null): string {
  return value && /^\d{4}-(0[1-9]|1[0-2])$/.test(value)
    ? value
    : currentMonth();
}

function monthWindow(month: string): { end: string; start: string } {
  const [year = 0, number = 1] = month.split("-").map(Number);
  const end = new Date(Date.UTC(year, number, 0)).toISOString().slice(0, 10);
  return { end, start: `${month}-01` };
}

function adjacentMonth(month: string, offset: number): string {
  const [year = 0, number = 1] = month.split("-").map(Number);
  return new Date(Date.UTC(year, number - 1 + offset, 1))
    .toISOString()
    .slice(0, 7);
}

function monthLabel(month: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "long",
    timeZone: "UTC",
    year: "numeric",
  }).format(new Date(`${month}-01T12:00:00Z`));
}

type CalendarLoadState =
  | { key: string; status: "pending" }
  | { calendar: ApplicationCalendar; key: string; status: "success" }
  | { key: string; message: string; status: "error" };

type ApplicationsLoadState =
  | { key: string; status: "pending" }
  | {
      applications: Application[];
      key: string;
      nextCursor: string | null;
      status: "success";
    }
  | { key: string; message: string; status: "error" };

export function ApplicationsView() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const routeKey = searchParams.toString();
  const query = searchParams.get("q")?.trim() ?? "";
  const stage = validStage(searchParams.get("stage"));
  const sort = validSort(searchParams.get("sort"));
  const outcome = validOutcome(searchParams.get("outcome"));
  const source = searchParams.get("source")?.trim() ?? "";
  const industry = searchParams.get("industry")?.trim() ?? "";
  const view = validView(searchParams.get("view"));
  const month = validMonth(searchParams.get("month"));
  const listKey = [query, stage, outcome, source, industry, sort]
    .map(encodeURIComponent)
    .join("|");
  const [listState, setListState] = useState<ApplicationsLoadState>();
  const listRequest = useRef(0);
  const [calendarState, setCalendarState] = useState<CalendarLoadState>();
  const calendarRequest = useRef(0);
  const [actionFailure, setActionFailure] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const [conflict, setConflict] = useState(false);
  const [busyId, setBusyId] = useState<string>();
  const [loadingMore, setLoadingMore] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const visibleListState = listState?.key === listKey ? listState : undefined;
  const applications =
    visibleListState?.status === "success"
      ? visibleListState.applications
      : undefined;
  const nextCursor =
    visibleListState?.status === "success"
      ? visibleListState.nextCursor
      : undefined;

  const replaceQuery = useCallback(
    (changes: Record<string, string | undefined>) => {
      const next = new URLSearchParams(routeKey);
      for (const [key, value] of Object.entries(changes)) {
        if (value) next.set(key, value);
        else next.delete(key);
      }
      const suffix = next.toString();
      router.replace(suffix ? `${pathname}?${suffix}` : pathname, {
        scroll: false,
      });
    },
    [pathname, routeKey, router],
  );

  const load = useCallback(async () => {
    const requestId = ++listRequest.current;
    setListState({ key: listKey, status: "pending" });
    setLoadingMore(false);
    setActionFailure(undefined);
    setConflict(false);
    try {
      const page = await listApplications({
        limit: 100,
        industry,
        outcome,
        q: query,
        sort,
        source,
        stage,
      });
      if (requestId !== listRequest.current) return;
      setListState({
        applications: page.data,
        key: listKey,
        nextCursor: page.page.nextCursor,
        status: "success",
      });
    } catch (error) {
      if (requestId !== listRequest.current) return;
      setListState({
        key: listKey,
        message: requestErrorMessage(
          error,
          "Applications could not be loaded.",
        ),
        status: "error",
      });
    }
  }, [industry, listKey, outcome, query, sort, source, stage]);

  const loadCalendar = useCallback(async () => {
    const requestId = ++calendarRequest.current;
    if (view !== "calendar") {
      setCalendarState(undefined);
      return;
    }
    const key = month;
    setCalendarState({ key, status: "pending" });
    try {
      const result = await getApplicationCalendar(monthWindow(month));
      if (requestId !== calendarRequest.current) return;
      setCalendarState({ calendar: result, key, status: "success" });
    } catch (error) {
      if (requestId !== calendarRequest.current) return;
      setCalendarState({
        key,
        message: requestErrorMessage(
          error,
          "The application calendar could not be loaded.",
        ),
        status: "error",
      });
    }
  }, [month, view]);

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) void load();
    });
    return () => {
      active = false;
      listRequest.current += 1;
    };
  }, [load]);

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) void loadCalendar();
    });
    return () => {
      active = false;
      calendarRequest.current += 1;
    };
  }, [loadCalendar]);

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    replaceQuery({
      industry: String(form.get("industry") ?? "").trim() || undefined,
      q: String(form.get("q") ?? "").trim() || undefined,
      source: String(form.get("source") ?? "").trim() || undefined,
    });
  }

  async function move(
    application: Application,
    nextStage: ApplicationStage,
    reopenReason?: string,
  ) {
    setBusyId(application.id);
    setActionFailure(undefined);
    setSuccess(undefined);
    setConflict(false);
    try {
      const updated = await updateApplicationStage(application, {
        ...(reopenReason ? { reopenReason } : {}),
        stage: nextStage,
      });
      setListState((current) =>
        current?.key === listKey && current.status === "success"
          ? {
              ...current,
              applications: current.applications
                .map((item) => (item.id === updated.id ? updated : item))
                .filter((item) => !stage || item.stage === stage),
            }
          : current,
      );
      setSuccess(`${updated.jobTitle} moved to ${humanize(updated.stage)}.`);
    } catch (error) {
      const stale =
        error instanceof ApiRequestError &&
        (error.failure.status === 409 || error.failure.status === 412);
      setConflict(stale);
      setActionFailure(
        stale
          ? "This application changed in another session. Reload before moving it again."
          : requestErrorMessage(
              error,
              "The application stage could not be moved.",
            ),
      );
    } finally {
      setBusyId(undefined);
    }
  }

  async function loadMore() {
    if (!nextCursor) return;
    const cursor = nextCursor;
    const requestId = ++listRequest.current;
    setLoadingMore(true);
    setActionFailure(undefined);
    try {
      const page = await listApplications({
        cursor,
        industry,
        limit: 100,
        outcome,
        q: query,
        sort,
        source,
        stage,
      });
      if (requestId !== listRequest.current) return;
      setListState((current) =>
        current?.key === listKey &&
        current.status === "success" &&
        current.nextCursor === cursor
          ? {
              applications: [...current.applications, ...page.data],
              key: listKey,
              nextCursor: page.page.nextCursor,
              status: "success",
            }
          : current,
      );
    } catch (error) {
      if (requestId !== listRequest.current) return;
      setActionFailure(
        requestErrorMessage(error, "More applications could not be loaded."),
      );
    } finally {
      if (requestId === listRequest.current) setLoadingMore(false);
    }
  }

  const filtered = Boolean(query || stage || outcome || source || industry);
  const visibleCalendarState =
    view === "calendar" && calendarState?.key === month
      ? calendarState
      : undefined;
  const viewIcon = useMemo(
    () => ({
      board: LayoutDashboard,
      calendar: CalendarDays,
      table: List,
    }),
    [],
  );

  if (visibleListState?.status === "error") {
    return (
      <main
        className="mx-auto max-w-[96rem] p-4 sm:p-6 lg:p-8"
        id="main-content"
      >
        <ErrorState
          description={visibleListState.message}
          onRetry={() => void load()}
          title="Application Workspace unavailable"
        />
      </main>
    );
  }

  if (!applications) {
    return <ApplicationsLoading />;
  }

  return (
    <main
      className="mx-auto max-w-[96rem] space-y-6 p-4 sm:p-6 lg:p-8"
      id="main-content"
    >
      <PageHeader
        actions={
          <Button
            onClick={() => {
              void load();
              if (view === "calendar") void loadCalendar();
            }}
            variant="secondary"
          >
            <RefreshCcw aria-hidden="true" className="size-4" />
            Refresh
          </Button>
        }
        description="Track opportunities, exact resume versions, follow-ups, and evidence-grounded application packs. Rezumi never submits an application on your behalf."
        eyebrow="Applications"
        title="Keep every application traceable"
      />

      {actionFailure && (
        <Alert
          title={conflict ? "Reload required" : "Action failed"}
          tone="danger"
        >
          <p>{actionFailure}</p>
          {conflict && (
            <Button className="mt-3 min-h-9 px-3" onClick={() => void load()}>
              Reload current data
            </Button>
          )}
        </Alert>
      )}
      {success && (
        <Alert title="Workspace updated" tone="success">
          {success}
        </Alert>
      )}

      <details
        className="rounded-card border border-border bg-surface-raised"
        onToggle={(event) => setCreateOpen(event.currentTarget.open)}
        open={createOpen}
      >
        <summary className="flex min-h-12 cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm font-black text-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary-soft">
          <Plus aria-hidden="true" className="size-4 text-primary" />
          Add an application
        </summary>
        <div className="border-t border-line p-4">
          {createOpen && (
            <CreateApplicationForm
              onCreated={(application) => {
                setSuccess(`${application.jobTitle} added to your workspace.`);
                setCreateOpen(false);
                void load();
              }}
            />
          )}
        </div>
      </details>

      <details
        className="rounded-card border border-border bg-surface-raised"
        onToggle={(event) => setProfileOpen(event.currentTarget.open)}
      >
        <summary className="flex min-h-12 cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm font-black text-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary-soft">
          <Settings2 aria-hidden="true" className="size-4 text-primary" />
          Application Profile (used by &ldquo;Apply for me&rdquo;)
        </summary>
        <div className="border-t border-line p-4">
          {profileOpen && <ApplicationProfilePanel />}
        </div>
      </details>

      <section
        aria-label="Application filters"
        className="rounded-card border border-border bg-surface-raised p-4"
      >
        <form
          className="grid gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-[minmax(14rem,1fr)_11rem_11rem_11rem_11rem_12rem_auto]"
          key={routeKey}
          onSubmit={search}
        >
          <label className="text-sm font-bold text-foreground">
            Search applications
            <Input
              className="mt-1"
              defaultValue={query}
              maxLength={160}
              name="q"
              placeholder="Job, company, location, or resume"
              type="search"
            />
          </label>
          <label className="text-sm font-bold text-foreground">
            Stage
            <Select
              className="mt-1"
              onChange={(event) =>
                replaceQuery({ stage: event.target.value || undefined })
              }
              value={stage}
            >
              <option value="">All stages</option>
              {applicationStages.map((item) => (
                <option key={item} value={item}>
                  {humanize(item)}
                </option>
              ))}
            </Select>
          </label>
          <label className="text-sm font-bold text-foreground">
            Outcome
            <Select
              className="mt-1"
              onChange={(event) =>
                replaceQuery({ outcome: event.target.value || undefined })
              }
              value={outcome}
            >
              <option value="">All outcomes</option>
              {outcomeStatuses.map((item) => (
                <option key={item} value={item}>
                  {humanize(item)}
                </option>
              ))}
            </Select>
          </label>
          <label className="text-sm font-bold text-foreground">
            Source
            <Input
              className="mt-1"
              defaultValue={source}
              maxLength={120}
              name="source"
            />
          </label>
          <label className="text-sm font-bold text-foreground">
            Industry
            <Input
              className="mt-1"
              defaultValue={industry}
              maxLength={120}
              name="industry"
            />
          </label>
          <label className="text-sm font-bold text-foreground">
            Sort
            <Select
              className="mt-1"
              onChange={(event) => replaceQuery({ sort: event.target.value })}
              value={sort}
            >
              {applicationSorts.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </Select>
          </label>
          <Button className="self-end" type="submit" variant="secondary">
            <Search aria-hidden="true" className="size-4" />
            Search
          </Button>
        </form>
        {filtered && (
          <Button
            className="mt-3"
            onClick={() => {
              replaceQuery({
                industry: undefined,
                outcome: undefined,
                q: undefined,
                source: undefined,
                stage: undefined,
              });
            }}
            variant="ghost"
          >
            Clear filters
          </Button>
        )}
      </section>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div aria-label="Application view" className="flex gap-1" role="group">
          {applicationViews.map((item) => {
            const Icon = viewIcon[item.value];
            return (
              <button
                aria-pressed={view === item.value}
                className={cn(
                  "flex min-h-11 items-center gap-2 rounded-control border px-3 text-sm font-bold transition focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary-soft",
                  view === item.value
                    ? "border-primary bg-primary text-white"
                    : "border-transparent bg-surface-raised text-muted hover:border-border hover:text-foreground",
                )}
                key={item.value}
                onClick={() =>
                  replaceQuery({
                    view: item.value === "board" ? undefined : item.value,
                  })
                }
                type="button"
              >
                <Icon aria-hidden="true" className="size-4" />
                {item.label}
              </button>
            );
          })}
        </div>
        <p className="text-sm text-muted">
          {applications.length} application
          {applications.length === 1 ? "" : "s"}
        </p>
      </div>

      {view === "calendar" && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-border bg-surface-raised p-3">
          <Button
            aria-label="Previous month"
            onClick={() => replaceQuery({ month: adjacentMonth(month, -1) })}
            className="min-h-9 px-3"
            variant="secondary"
          >
            <ChevronLeft aria-hidden="true" className="size-4" />
          </Button>
          <h2 className="text-base font-black text-foreground">
            {monthLabel(month)}
          </h2>
          <div className="flex gap-2">
            <Button
              onClick={() =>
                replaceQuery({
                  month: currentMonth() === month ? undefined : currentMonth(),
                })
              }
              className="min-h-9 px-3"
              variant="ghost"
            >
              Today
            </Button>
            <Button
              aria-label="Next month"
              onClick={() => replaceQuery({ month: adjacentMonth(month, 1) })}
              className="min-h-9 px-3"
              variant="secondary"
            >
              <ChevronRight aria-hidden="true" className="size-4" />
            </Button>
          </div>
        </div>
      )}

      {applications.length === 0 && view !== "calendar" ? (
        <ApplicationCollectionEmpty filtered={filtered} />
      ) : view === "table" ? (
        <ApplicationTable
          applications={applications}
          busyId={busyId}
          onMove={(application, nextStage, reopenReason) =>
            void move(application, nextStage, reopenReason)
          }
        />
      ) : view === "calendar" ? (
        visibleCalendarState?.status === "success" ? (
          <ApplicationAgenda calendar={visibleCalendarState.calendar} />
        ) : visibleCalendarState?.status === "error" ? (
          <ErrorState
            description={visibleCalendarState.message}
            onRetry={() => void loadCalendar()}
            title="Calendar unavailable"
          />
        ) : (
          <LoadingSkeleton variant="list" />
        )
      ) : (
        <ApplicationBoard
          applications={applications}
          busyId={busyId}
          onMove={(application, nextStage, reopenReason) =>
            void move(application, nextStage, reopenReason)
          }
        />
      )}

      {nextCursor && view !== "calendar" && (
        <div className="flex justify-center">
          <Button
            loading={loadingMore}
            onClick={() => void loadMore()}
            variant="secondary"
          >
            Load more applications
          </Button>
        </div>
      )}
    </main>
  );
}

export function ApplicationsLoading() {
  return (
    <main className="mx-auto max-w-[96rem] p-4 sm:p-6 lg:p-8" id="main-content">
      <LoadingSkeleton variant="page" />
    </main>
  );
}

export function ApplicationsRouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto max-w-[96rem] p-4 sm:p-6 lg:p-8" id="main-content">
      <ErrorState
        description={error.message || "Refresh and try again."}
        onRetry={reset}
        title="Application Workspace unavailable"
      />
    </main>
  );
}
