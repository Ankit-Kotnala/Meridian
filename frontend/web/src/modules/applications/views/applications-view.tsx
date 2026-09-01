"use client";

import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  LayoutDashboard,
  List,
  RefreshCcw,
  Search,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";

import {
  Alert,
  Button,
  EmptyState,
  ErrorState,
  Input,
  LoadingSkeleton,
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
  ApplicationTable,
} from "../components/application-collection";
import {
  applicationSorts,
  applicationStages,
  applicationViews,
  humanize,
  outcomeStatuses,
} from "../components/application-options";

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

const viewIcon = {
  board: LayoutDashboard,
  calendar: CalendarDays,
  table: List,
} as const;

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
      const window = monthWindow(month);
      const calendar = await getApplicationCalendar({
        end: window.end,
        start: window.start,
      });
      if (requestId !== calendarRequest.current) return;
      setCalendarState({ calendar, key, status: "success" });
    } catch (error) {
      if (requestId !== calendarRequest.current) return;
      setCalendarState({
        key,
        message: requestErrorMessage(error, "Calendar could not be loaded."),
        status: "error",
      });
    }
  }, [month, view]);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  useEffect(() => {
    queueMicrotask(() => void loadCalendar());
  }, [loadCalendar]);

  const filtered = Boolean(query || stage || outcome || source || industry);
  const visibleCalendarState =
    calendarState?.key === month ? calendarState : undefined;

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    replaceQuery({
      industry: String(form.get("industry") ?? "").trim() || undefined,
      q: String(form.get("q") ?? "").trim() || undefined,
      source: String(form.get("source") ?? "").trim() || undefined,
    });
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

  const countLabel = applications
    ? `${applications.length} application${applications.length === 1 ? "" : "s"}`
    : null;

  if (visibleListState?.status === "error") {
    return (
      <main className="workspace-page" id="main-content">
        <ErrorState
          description={visibleListState.message}
          onRetry={() => void load()}
          title="Applications unavailable"
        />
      </main>
    );
  }

  if (!applications) {
    return <ApplicationsLoading />;
  }

  return (
    <main className="workspace-page space-y-6" id="main-content">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <p className="text-[0.6875rem] font-bold uppercase tracking-[0.14em] text-primary">
            Applications
          </p>
          <h1 className="mt-1.5 text-[1.625rem] font-bold tracking-[-0.03em] text-foreground sm:text-[1.75rem]">
            Track every application
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
            Applications appear here after you use Apply for me on a saved job.
            Keep reusable portal answers in Settings. Meridian never submits on
            your behalf.
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Link
            className="inline-flex min-h-11 items-center justify-center rounded-[var(--radius-control)] border border-line bg-surface px-4 text-sm font-semibold text-foreground hover:border-line-strong hover:bg-surface-subtle"
            href="/settings/application-answers"
          >
            Application answers
          </Link>
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
        </div>
      </header>

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
        <Alert title="Updated" tone="success">
          {success}
        </Alert>
      )}

      <section
        aria-label="Application filters"
        className="rounded-[var(--radius-card)] border border-line bg-surface p-4"
      >
        <form
          className="grid gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-[minmax(14rem,1fr)_10rem_10rem_10rem_10rem_11rem_auto]"
          key={routeKey}
          onSubmit={search}
        >
          <label className="text-sm font-semibold text-foreground">
            Search
            <Input
              className="mt-1.5"
              defaultValue={query}
              maxLength={160}
              name="q"
              placeholder="Job, company, location, or keyword"
              type="search"
            />
          </label>
          <label className="text-sm font-semibold text-foreground">
            Stage
            <Select
              className="mt-1.5"
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
          <label className="text-sm font-semibold text-foreground">
            Outcome
            <Select
              className="mt-1.5"
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
          <label className="text-sm font-semibold text-foreground">
            Source
            <Input
              className="mt-1.5"
              defaultValue={source}
              maxLength={120}
              name="source"
            />
          </label>
          <label className="text-sm font-semibold text-foreground">
            Industry
            <Input
              className="mt-1.5"
              defaultValue={industry}
              maxLength={120}
              name="industry"
            />
          </label>
          <label className="text-sm font-semibold text-foreground">
            Sort
            <Select
              className="mt-1.5"
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
        <div
          aria-label="Application view"
          className="inline-flex gap-1 rounded-[var(--radius-control)] border border-line bg-surface p-1"
          role="group"
        >
          {applicationViews.map((item) => {
            const Icon = viewIcon[item.value];
            const active = view === item.value;
            return (
              <button
                aria-pressed={active}
                className={cn(
                  "flex min-h-9 items-center gap-2 rounded-[calc(var(--radius-control)-0.125rem)] px-3 text-[0.8125rem] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary-soft",
                  active
                    ? "bg-primary text-white"
                    : "text-muted-strong hover:bg-surface-subtle hover:text-foreground",
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
        {countLabel && <p className="text-sm text-muted">{countLabel}</p>}
      </div>

      {view === "calendar" && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-card)] border border-line bg-surface p-3">
          <Button
            aria-label="Previous month"
            className="min-h-9 px-3"
            onClick={() => replaceQuery({ month: adjacentMonth(month, -1) })}
            variant="secondary"
          >
            <ChevronLeft aria-hidden="true" className="size-4" />
          </Button>
          <h2 className="text-base font-semibold text-foreground">
            {monthLabel(month)}
          </h2>
          <div className="flex gap-2">
            <Button
              className="min-h-9 px-3"
              onClick={() =>
                replaceQuery({
                  month: currentMonth() === month ? undefined : currentMonth(),
                })
              }
              variant="ghost"
            >
              Today
            </Button>
            <Button
              aria-label="Next month"
              className="min-h-9 px-3"
              onClick={() => replaceQuery({ month: adjacentMonth(month, 1) })}
              variant="secondary"
            >
              <ChevronRight aria-hidden="true" className="size-4" />
            </Button>
          </div>
        </div>
      )}

      {applications.length === 0 && view !== "calendar" ? (
        <EmptyState
          action={
            filtered ? undefined : (
              <Link
                className={cn(
                  "mt-4 inline-flex min-h-10 items-center justify-center rounded-[var(--radius-control)] border border-primary bg-primary px-4 text-sm font-semibold text-white hover:border-primary-strong hover:bg-primary-strong",
                )}
                href="/job-match"
              >
                Open Job search
              </Link>
            )
          }
          description={
            filtered
              ? "Adjust or clear the current search and filters."
              : "Save a job in Job search, then use Apply for me. It will show up here to track."
          }
          title={filtered ? "No matching applications" : "No applications yet"}
        />
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
    <main className="workspace-page" id="main-content">
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
    <main className="workspace-page" id="main-content">
      <ErrorState
        description={error.message || "Refresh and try again."}
        onRetry={reset}
        title="Applications unavailable"
      />
    </main>
  );
}
