"use client";

import {
  BookOpenCheck,
  CalendarPlus,
  ChevronRight,
  RefreshCcw,
  Route,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  CheckboxField,
  EmptyState,
  ErrorState,
  Input,
  LoadingSkeleton,
  Select,
  buttonStyles,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  createSession,
  createStory,
  getDefenseMap,
  listInterviewApplications,
  listSessions,
  listStories,
} from "../api/interview-prep-api";
import type {
  ApplicationSummary,
  DefenseMap,
  InterviewSession,
  InterviewSessionKind,
  InterviewSessionSummary,
  StarStory,
  StarStorySummary,
  StoryField,
  StoryStatus,
} from "../api/types";
import { useIntentActivity } from "../state/use-intent-activity";

const storyStatuses: readonly StoryStatus[] = ["draft", "ready", "archived"];
const sessionKinds: readonly InterviewSessionKind[] = [
  "recruiter_screen",
  "behavioral",
  "technical",
  "hiring_manager",
  "panel",
  "other",
];
const storyFields: ReadonlyArray<{ label: string; value: StoryField }> = [
  { label: "Situation", value: "situation" },
  { label: "Task", value: "task" },
  { label: "Action", value: "action" },
  { label: "Result", value: "result" },
  { label: "Personal contribution", value: "personal_contribution" },
  { label: "Metric explanation", value: "metric_explanation" },
];

const fieldClass =
  "min-h-28 w-full rounded-[var(--radius-control)] border border-line-strong bg-surface px-3.5 py-3 text-sm font-normal text-foreground outline-none placeholder:text-muted hover:border-primary/70 focus:border-primary focus:ring-3 focus:ring-primary-soft disabled:cursor-not-allowed disabled:bg-surface-subtle";

function humanize(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function dateTime(value: string | null): string {
  if (!value) return "Not scheduled";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function toneForDefense(status: string) {
  if (status === "defended") return "success" as const;
  if (status === "partial") return "warning" as const;
  return "danger" as const;
}

function toneForStory(status: StoryStatus) {
  if (status === "ready") return "success" as const;
  if (status === "archived") return "neutral" as const;
  return "warning" as const;
}

function applicationLabel(application: ApplicationSummary): string {
  return [application.jobTitle, application.company]
    .filter(Boolean)
    .join(" — ");
}

function storySummary(story: StarStory): StarStorySummary {
  return {
    applicationId: story.applicationId,
    claimCount: story.claimPins.length,
    confidence: story.confidence,
    createdAt: story.createdAt,
    groundingStatus: story.groundingStatus,
    groundingWarning: story.groundingWarning,
    id: story.id,
    origin: story.origin,
    status: story.status,
    title: story.title,
    updatedAt: story.updatedAt,
    version: story.version,
  };
}

function sessionSummary(session: InterviewSession): InterviewSessionSummary {
  return {
    applicationId: session.applicationId,
    company: session.context.company,
    createdAt: session.createdAt,
    followUpDraftCount: session.followUpDraftCount,
    groundingStatus: session.groundingStatus,
    groundingWarning: session.groundingWarning,
    id: session.id,
    jobTitle: session.context.jobTitle,
    kind: session.kind,
    noteCount: session.noteCount,
    questionBankGenerated: session.questionBankGenerated,
    questionBankId: session.questionBankId,
    questionCount: session.questionCount,
    scheduledAt: session.scheduledAt,
    title: session.title,
    updatedAt: session.updatedAt,
    version: session.version,
  };
}

function mergeById<T extends { id: string }>(
  current: readonly T[],
  incoming: readonly T[],
): T[] {
  const byId = new Map(current.map((item) => [item.id, item]));
  for (const item of incoming) byId.set(item.id, item);
  return [...byId.values()];
}

type CollectionState =
  | { status: "loading" }
  | {
      applications: ApplicationSummary[];
      applicationCursor: string | null;
      sessions: InterviewSessionSummary[];
      sessionCursor: string | null;
      stories: StarStorySummary[];
      storyCursor: string | null;
      status: "ready";
    }
  | { message: string; status: "error" };

export function InterviewPrepView({
  roadmapPanel,
}: {
  roadmapPanel: ReactNode;
}) {
  const [state, setState] = useState<CollectionState>({ status: "loading" });
  const [applicationId, setApplicationId] = useState("");
  const [storyStatus, setStoryStatus] = useState<StoryStatus | "">("");
  const [defenseMap, setDefenseMap] = useState<DefenseMap>();
  const [defenseFailure, setDefenseFailure] = useState<string>();
  const [actionFailure, setActionFailure] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const {
    begin: beginIntentActivity,
    end: endIntentActivity,
    isActive: isIntentActive,
  } = useIntentActivity();
  const [showStoryForm, setShowStoryForm] = useState(false);
  const [showSessionForm, setShowSessionForm] = useState(false);
  const loadEpoch = useRef(0);
  const loadController = useRef<AbortController | null>(null);
  const defenseEpoch = useRef(0);
  const defenseController = useRef<AbortController | null>(null);
  const intentKeys = useRef(new Map<string, string>());

  const stableIntent = useCallback((intent: string) => {
    const existing = intentKeys.current.get(intent);
    if (existing) return existing;
    const key = `interview-web:${crypto.randomUUID()}`;
    intentKeys.current.set(intent, key);
    return key;
  }, []);

  const clearIntent = useCallback((intent: string) => {
    intentKeys.current.delete(intent);
  }, []);

  const load = useCallback(async () => {
    loadController.current?.abort();
    const controller = new AbortController();
    loadController.current = controller;
    const epoch = ++loadEpoch.current;
    setState({ status: "loading" });
    setActionFailure(undefined);
    try {
      const [applications, stories, sessions] = await Promise.all([
        listInterviewApplications({ limit: 100, signal: controller.signal }),
        listStories({
          ...(applicationId ? { applicationId } : {}),
          limit: 50,
          signal: controller.signal,
          status: storyStatus,
        }),
        listSessions({
          ...(applicationId ? { applicationId } : {}),
          limit: 50,
          signal: controller.signal,
        }),
      ]);
      if (epoch !== loadEpoch.current || controller.signal.aborted) return;
      setState({
        applications: applications.data,
        applicationCursor: applications.page.nextCursor,
        sessions: sessions.data,
        sessionCursor: sessions.page.nextCursor,
        stories: stories.data,
        storyCursor: stories.page.nextCursor,
        status: "ready",
      });
    } catch (error) {
      if (controller.signal.aborted || epoch !== loadEpoch.current) return;
      setState({
        message: requestErrorMessage(
          error,
          "Interview Prep could not be loaded.",
        ),
        status: "error",
      });
    }
  }, [applicationId, storyStatus]);

  const loadDefense = useCallback(async () => {
    defenseController.current?.abort();
    const controller = new AbortController();
    defenseController.current = controller;
    const epoch = ++defenseEpoch.current;
    setDefenseFailure(undefined);
    setDefenseMap(undefined);
    if (!applicationId) return;
    try {
      const result = await getDefenseMap(applicationId, controller.signal);
      if (epoch !== defenseEpoch.current || controller.signal.aborted) return;
      setDefenseMap(result);
    } catch (error) {
      if (controller.signal.aborted || epoch !== defenseEpoch.current) return;
      setDefenseFailure(
        requestErrorMessage(
          error,
          "The resume defense map could not be loaded.",
        ),
      );
    }
  }, [applicationId]);

  useEffect(() => {
    queueMicrotask(() => void load());
    return () => {
      loadController.current?.abort();
      loadEpoch.current += 1;
    };
  }, [load]);

  useEffect(() => {
    queueMicrotask(() => void loadDefense());
    return () => {
      defenseController.current?.abort();
      defenseEpoch.current += 1;
    };
  }, [loadDefense]);

  const selectedApplication = useMemo(
    () =>
      state.status === "ready"
        ? state.applications.find((item) => item.id === applicationId)
        : undefined,
    [applicationId, state],
  );

  async function loadMore(kind: "applications" | "sessions" | "stories") {
    if (state.status !== "ready") return;
    const cursor =
      kind === "applications"
        ? state.applicationCursor
        : kind === "sessions"
          ? state.sessionCursor
          : state.storyCursor;
    if (!cursor) return;
    const epoch = loadEpoch.current;
    const activity = beginIntentActivity(`more-${kind}`);
    setActionFailure(undefined);
    try {
      if (kind === "applications") {
        const page = await listInterviewApplications({ cursor, limit: 100 });
        if (epoch !== loadEpoch.current) return;
        setState((current) =>
          current.status === "ready" && current.applicationCursor === cursor
            ? {
                ...current,
                applications: mergeById(current.applications, page.data),
                applicationCursor: page.page.nextCursor,
              }
            : current,
        );
      } else if (kind === "stories") {
        const page = await listStories({
          ...(applicationId ? { applicationId } : {}),
          cursor,
          limit: 50,
          status: storyStatus,
        });
        if (epoch !== loadEpoch.current) return;
        setState((current) =>
          current.status === "ready" && current.storyCursor === cursor
            ? {
                ...current,
                stories: mergeById(current.stories, page.data),
                storyCursor: page.page.nextCursor,
              }
            : current,
        );
      } else {
        const page = await listSessions({
          ...(applicationId ? { applicationId } : {}),
          cursor,
          limit: 50,
        });
        if (epoch !== loadEpoch.current) return;
        setState((current) =>
          current.status === "ready" && current.sessionCursor === cursor
            ? {
                ...current,
                sessions: mergeById(current.sessions, page.data),
                sessionCursor: page.page.nextCursor,
              }
            : current,
        );
      }
    } catch (error) {
      if (epoch !== loadEpoch.current) return;
      setActionFailure(
        requestErrorMessage(error, `More ${kind} could not be loaded.`),
      );
    } finally {
      endIntentActivity(activity);
    }
  }

  async function submitStory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!applicationId || !defenseMap) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const selectedClaims = form.getAll("claimId").map(String);
    const selectedFields = form.getAll("fieldName") as StoryField[];
    if (selectedClaims.length === 0 || selectedFields.length === 0) {
      setActionFailure(
        "Choose at least one claim and one STAR field to create a provenance pin.",
      );
      return;
    }
    const input = {
      action: String(form.get("action") ?? "").trim(),
      applicationId,
      claimSelections: selectedClaims.map((claimId) => ({
        claimId,
        fieldNames: selectedFields,
      })),
      confidence: Number(form.get("confidence")),
      followUpQuestions: String(form.get("followUpQuestions") ?? "")
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean),
      metricExplanation:
        String(form.get("metricExplanation") ?? "").trim() || null,
      personalContribution: String(
        form.get("personalContribution") ?? "",
      ).trim(),
      result: String(form.get("result") ?? "").trim(),
      situation: String(form.get("situation") ?? "").trim(),
      status: String(form.get("status")) as StoryStatus,
      task: String(form.get("task") ?? "").trim(),
      title: String(form.get("title") ?? "").trim(),
    };
    const intent = `story:${JSON.stringify(input)}`;
    const activity = beginIntentActivity("create-story");
    setActionFailure(undefined);
    setSuccess(undefined);
    try {
      const story = await createStory(input, stableIntent(intent));
      clearIntent(intent);
      setState((current) =>
        current.status === "ready"
          ? {
              ...current,
              stories: [
                storySummary(story),
                ...current.stories.filter((item) => item.id !== story.id),
              ],
            }
          : current,
      );
      setSuccess(
        `${story.title} saved with exact claim and evidence revision pins.`,
      );
      setShowStoryForm(false);
      formElement.reset();
      await loadDefense();
    } catch (error) {
      setActionFailure(
        requestErrorMessage(error, "The STAR story could not be saved."),
      );
    } finally {
      endIntentActivity(activity);
    }
  }

  async function submitSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!applicationId) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const scheduled = String(form.get("scheduledAt") ?? "");
    const input = {
      applicationId,
      kind: String(form.get("kind")) as InterviewSessionKind,
      scheduledAt: scheduled ? new Date(scheduled).toISOString() : null,
      title: String(form.get("title") ?? "").trim(),
    };
    const intent = `session:${JSON.stringify(input)}`;
    const activity = beginIntentActivity("create-session");
    setActionFailure(undefined);
    setSuccess(undefined);
    try {
      const session = await createSession(input, stableIntent(intent));
      clearIntent(intent);
      setState((current) =>
        current.status === "ready"
          ? {
              ...current,
              sessions: [
                sessionSummary(session),
                ...current.sessions.filter((item) => item.id !== session.id),
              ],
            }
          : current,
      );
      setSuccess(`${session.title} created from an immutable bounded context.`);
      setShowSessionForm(false);
      formElement.reset();
    } catch (error) {
      setActionFailure(
        requestErrorMessage(
          error,
          "The interview session could not be created.",
        ),
      );
    } finally {
      endIntentActivity(activity);
    }
  }

  if (state.status === "error") {
    return (
      <main className="workspace-page" id="main-content">
        <ErrorState
          description={state.message}
          onRetry={() => void load()}
          title="Interview Prep unavailable"
        />
      </main>
    );
  }

  if (state.status === "loading") {
    return (
      <main className="workspace-page" id="main-content">
        <LoadingSkeleton variant="page" />
      </main>
    );
  }

  return (
    <main className="workspace-page space-y-7" id="main-content">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <p className="text-[0.6875rem] font-bold uppercase tracking-[0.14em] text-primary">
            Interview Prep
          </p>
          <h1 className="mt-1.5 text-[1.625rem] font-bold tracking-[-0.03em] text-foreground sm:text-[1.75rem]">
            Prepare with a plan built around you
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            Start with the skills your target role calls for, then turn your
            evidence into defensible stories and focused practice sessions.
            Meridian never sends a message or invents a missing fact.
          </p>
        </div>
        <Button
          className="shrink-0"
          onClick={() => void load()}
          variant="secondary"
        >
          <RefreshCcw aria-hidden="true" className="size-4" />
          Refresh practice
        </Button>
      </header>

      <section
        aria-labelledby="personalized-roadmap-heading"
        className="space-y-4"
      >
        <div className="flex items-start gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary">
            <Route aria-hidden="true" className="size-5" />
          </span>
          <div>
            <h2
              className="text-lg font-semibold tracking-[-0.02em] text-foreground"
              id="personalized-roadmap-heading"
            >
              Personalized interview roadmap
            </h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
              Follow the staged path for your target role. Hover a stop or open
              it to see why it matters and a first practice step. Resume and
              Career Record evidence marks what is already demonstrated versus
              what still deserves attention.
            </p>
          </div>
        </div>
        {roadmapPanel}
      </section>

      {actionFailure && (
        <Alert title="Action failed" tone="danger">
          {actionFailure}
        </Alert>
      )}
      {success && (
        <Alert title="Interview Prep updated" tone="success">
          {success}
        </Alert>
      )}

      <section
        aria-label="Interview filters"
        className="rounded-[var(--radius-card)] border border-line bg-surface p-4"
      >
        <div className="grid gap-3 md:grid-cols-[minmax(0,2fr)_minmax(12rem,1fr)]">
          <label
            className="text-sm font-semibold text-foreground"
            htmlFor="interview-application"
          >
            Application context
            <Select
              className="mt-1.5"
              id="interview-application"
              onChange={(event) => setApplicationId(event.target.value)}
              value={applicationId}
            >
              <option value="">Choose an application</option>
              {state.applications.map((application) => (
                <option key={application.id} value={application.id}>
                  {applicationLabel(application)}
                </option>
              ))}
            </Select>
          </label>
          <label
            className="text-sm font-semibold text-foreground"
            htmlFor="story-status-filter"
          >
            Story status
            <Select
              className="mt-1.5"
              id="story-status-filter"
              onChange={(event) =>
                setStoryStatus(event.target.value as StoryStatus | "")
              }
              value={storyStatus}
            >
              <option value="">All story statuses</option>
              {storyStatuses.map((status) => (
                <option key={status} value={status}>
                  {humanize(status)}
                </option>
              ))}
            </Select>
          </label>
        </div>
        {state.applicationCursor && (
          <Button
            className="mt-3 min-h-9 px-3"
            disabled={isIntentActive("more-applications")}
            onClick={() => void loadMore("applications")}
            variant="ghost"
          >
            Load more applications
          </Button>
        )}
      </section>

      {!applicationId ? (
        <EmptyState
          action={
            state.applications.length === 0 ? (
              <Link
                className={`${buttonStyles.base} ${buttonStyles.primary} mt-4`}
                href="/applications"
              >
                Open Applications
              </Link>
            ) : undefined
          }
          description={
            state.applications.length === 0
              ? "Applications appear after you use Apply for me on a saved job. Choose one here to ground stories and sessions in its claims."
              : "Select an application above. Only its bounded claim, requirement, and evidence pins are used."
          }
          title={
            state.applications.length === 0
              ? "No applications yet"
              : "Choose an application"
          }
        />
      ) : (
        <>
          <section aria-labelledby="defense-map-heading" className="space-y-4">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2
                  className="text-lg font-semibold tracking-[-0.02em] text-foreground"
                  id="defense-map-heading"
                >
                  Resume Defense Map
                </h2>
                <p className="mt-1 text-sm leading-6 text-muted">
                  Exact immutable claims
                  {selectedApplication
                    ? ` for ${applicationLabel(selectedApplication)}`
                    : ""}
                  .
                </p>
              </div>
              <Button
                disabled={!defenseMap}
                onClick={() => setShowStoryForm((open) => !open)}
              >
                <BookOpenCheck aria-hidden="true" className="size-4" />
                {showStoryForm ? "Close story form" : "Add STAR story"}
              </Button>
            </div>

            {defenseFailure && (
              <ErrorState
                description={defenseFailure}
                onRetry={() => void loadDefense()}
                title="Defense map unavailable"
              />
            )}
            {!defenseMap && !defenseFailure && (
              <LoadingSkeleton className="py-2" />
            )}
            {defenseMap && (
              <>
                <p className="text-sm text-muted">
                  <span className="font-semibold text-foreground">
                    {defenseMap.defendedCount}
                  </span>{" "}
                  defended ·{" "}
                  <span className="font-semibold text-foreground">
                    {defenseMap.partialCount}
                  </span>{" "}
                  partial ·{" "}
                  <span className="font-semibold text-foreground">
                    {defenseMap.undefendedCount}
                  </span>{" "}
                  undefended
                  {defenseMap.strongClaimWarningCount > 0
                    ? ` · ${defenseMap.strongClaimWarningCount} strong-claim warning${
                        defenseMap.strongClaimWarningCount === 1 ? "" : "s"
                      }`
                    : ""}
                </p>
                {defenseMap.entries.length === 0 ? (
                  <EmptyState
                    description="This application has no eligible pinned claims to defend."
                    title="No defensible claims"
                  />
                ) : (
                  <ul className="grid gap-3 lg:grid-cols-2">
                    {defenseMap.entries.map((entry) => (
                      <li
                        className="rounded-[var(--radius-card)] border border-line bg-surface p-4"
                        key={entry.claimId}
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge tone={toneForDefense(entry.status)}>
                            {humanize(entry.status)}
                          </Badge>
                          {entry.strong && (
                            <Badge tone="warning">Strong claim</Badge>
                          )}
                          <span className="text-xs font-semibold text-muted">
                            {entry.evidenceRevisionIds.length} exact evidence{" "}
                            {entry.evidenceRevisionIds.length === 1
                              ? "revision"
                              : "revisions"}
                          </span>
                        </div>
                        <p className="mt-3 text-sm leading-6 text-foreground">
                          {entry.claimText}
                        </p>
                        {entry.warning && (
                          <p className="mt-3 text-sm font-semibold text-danger">
                            Warning: {entry.warning}
                          </p>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </section>

          {showStoryForm && defenseMap && (
            <StoryCreateForm
              busy={isIntentActive("create-story")}
              defenseMap={defenseMap}
              onSubmit={submitStory}
            />
          )}

          <section
            aria-labelledby="story-library-heading"
            className="space-y-4"
          >
            <div>
              <h2
                className="text-lg font-semibold tracking-[-0.02em] text-foreground"
                id="story-library-heading"
              >
                STAR stories
              </h2>
              <p className="mt-1 text-sm leading-6 text-muted">
                Confidence is your own preparedness assessment, not an employer
                score.
              </p>
            </div>
            {state.stories.length === 0 ? (
              <EmptyState
                action={
                  <Button
                    disabled={!defenseMap}
                    onClick={() => setShowStoryForm(true)}
                  >
                    Add a story
                  </Button>
                }
                description="Create a structured story from exact eligible application claims and evidence revisions."
                title="No STAR stories yet"
              />
            ) : (
              <ul className="grid gap-3 lg:grid-cols-2">
                {state.stories.map((story) => (
                  <li
                    className="rounded-[var(--radius-card)] border border-line bg-surface p-4"
                    key={story.id}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={toneForStory(story.status)}>
                        {humanize(story.status)}
                      </Badge>
                      <Badge tone="neutral">
                        Confidence {story.confidence} of 5
                      </Badge>
                      <Badge
                        tone={
                          story.groundingStatus === "current"
                            ? "success"
                            : story.groundingStatus === "needs_review"
                              ? "warning"
                              : "neutral"
                        }
                      >
                        {story.groundingStatus === "current"
                          ? "Evidence current"
                          : humanize(story.groundingStatus)}
                      </Badge>
                      <span className="text-xs font-semibold text-muted">
                        {story.claimCount} pinned{" "}
                        {story.claimCount === 1 ? "claim" : "claims"}
                      </span>
                    </div>
                    <h3 className="mt-3 font-semibold text-foreground">
                      {story.title}
                    </h3>
                    {story.groundingWarning && (
                      <p className="mt-2 text-sm font-semibold leading-6 text-warning-strong">
                        {story.groundingWarning}
                      </p>
                    )}
                    <Link
                      className={`${buttonStyles.base} ${buttonStyles.ghost} mt-3 -ml-3`}
                      href={`/interview-prep/stories/${story.id}`}
                    >
                      Review story
                      <ChevronRight aria-hidden="true" className="size-4" />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            {state.storyCursor && (
              <Button
                disabled={isIntentActive("more-stories")}
                onClick={() => void loadMore("stories")}
                variant="secondary"
              >
                Load more stories
              </Button>
            )}
          </section>

          <section aria-labelledby="sessions-heading" className="space-y-4">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2
                  className="text-lg font-semibold tracking-[-0.02em] text-foreground"
                  id="sessions-heading"
                >
                  Interview sessions
                </h2>
                <p className="mt-1 text-sm leading-6 text-muted">
                  Questions and notes stay private inside this workspace.
                </p>
              </div>
              <Button
                onClick={() => setShowSessionForm((open) => !open)}
                variant="secondary"
              >
                <CalendarPlus aria-hidden="true" className="size-4" />
                {showSessionForm ? "Close session form" : "Create session"}
              </Button>
            </div>
            {showSessionForm && (
              <SessionCreateForm
                busy={isIntentActive("create-session")}
                onSubmit={submitSession}
              />
            )}
            {state.sessions.length === 0 ? (
              <EmptyState
                description="Create a session to snapshot bounded role, requirement, claim, and evidence context."
                title="No interview sessions"
              />
            ) : (
              <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {state.sessions.map((session) => (
                  <li
                    className="rounded-[var(--radius-card)] border border-line bg-surface p-4"
                    key={session.id}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone="primary">{humanize(session.kind)}</Badge>
                      <Badge
                        tone={
                          session.groundingStatus === "current"
                            ? "success"
                            : session.groundingStatus === "needs_review"
                              ? "warning"
                              : "neutral"
                        }
                      >
                        {session.groundingStatus === "current"
                          ? "Evidence current"
                          : humanize(session.groundingStatus)}
                      </Badge>
                      <span className="text-xs font-semibold text-muted">
                        {dateTime(session.scheduledAt)}
                      </span>
                    </div>
                    <h3 className="mt-3 font-semibold text-foreground">
                      {session.title}
                    </h3>
                    <p className="mt-1 text-sm text-muted">
                      {session.jobTitle}
                      {session.company ? ` at ${session.company}` : ""}
                    </p>
                    {session.groundingWarning && (
                      <p className="mt-2 text-sm font-semibold text-warning-strong">
                        {session.groundingWarning}
                      </p>
                    )}
                    <p className="mt-3 text-xs font-semibold text-muted">
                      {session.questionCount} questions · {session.noteCount}{" "}
                      private notes · {session.followUpDraftCount} drafts
                    </p>
                    <Link
                      className={`${buttonStyles.base} ${buttonStyles.ghost} mt-3 -ml-3`}
                      href={`/interview-prep/sessions/${session.id}`}
                    >
                      Open session
                      <ChevronRight aria-hidden="true" className="size-4" />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            {state.sessionCursor && (
              <Button
                disabled={isIntentActive("more-sessions")}
                onClick={() => void loadMore("sessions")}
                variant="secondary"
              >
                Load more sessions
              </Button>
            )}
          </section>
        </>
      )}
    </main>
  );
}

function StoryCreateForm({
  busy,
  defenseMap,
  onSubmit,
}: {
  busy: boolean;
  defenseMap: DefenseMap;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <Card className="p-4 sm:p-5">
      <form className="space-y-5" onSubmit={onSubmit}>
        <div>
          <h2 className="text-lg font-semibold tracking-[-0.02em] text-foreground">
            Add an evidence-linked STAR story
          </h2>
          <p className="mt-1 text-sm text-muted">
            Selected claims resolve to their exact eligible evidence revision
            numbers and hashes. Missing facts must stay out of the story.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <LabeledInput
            id="story-title"
            label="Story title"
            name="title"
            required
          />
          <label className="space-y-2 text-sm font-semibold text-foreground">
            Confidence
            <Select defaultValue="3" name="confidence" required>
              {[1, 2, 3, 4, 5].map((value) => (
                <option key={value} value={value}>
                  {value} of 5
                </option>
              ))}
            </Select>
          </label>
          <label className="space-y-2 text-sm font-semibold text-foreground">
            Story status
            <Select defaultValue="draft" name="status">
              {storyStatuses.map((status) => (
                <option key={status} value={status}>
                  {humanize(status)}
                </option>
              ))}
            </Select>
          </label>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          {[
            ["Situation", "situation", 2000],
            ["Task", "task", 2000],
            ["Action", "action", 3000],
            ["Result", "result", 2000],
            ["Personal contribution", "personalContribution", 2000],
            [
              "Metric explanation (required for any number)",
              "metricExplanation",
              2000,
            ],
          ].map(([label, name, maxLength]) => (
            <LabeledTextarea
              id={`story-${name}`}
              key={String(name)}
              label={String(label)}
              maxLength={Number(maxLength)}
              name={String(name)}
              required={name !== "metricExplanation"}
            />
          ))}
        </div>
        <LabeledTextarea
          hint="One question per line; up to 12."
          id="story-follow-up"
          label="Likely follow-up questions"
          maxLength={6000}
          name="followUpQuestions"
        />
        <fieldset className="space-y-3 rounded-xl border border-line p-4">
          <legend className="px-1 text-sm font-semibold text-foreground">
            Exact claims to pin
          </legend>
          {defenseMap.entries.map((entry) => (
            <CheckboxField
              description={`${humanize(entry.status)} · ${
                entry.evidenceRevisionIds.length
              } eligible evidence revision(s)`}
              id={`story-claim-${entry.claimId}`}
              key={entry.claimId}
              label={entry.claimText}
              name="claimId"
              value={entry.claimId}
            />
          ))}
        </fieldset>
        <fieldset className="grid gap-3 rounded-xl border border-line p-4 sm:grid-cols-2 lg:grid-cols-3">
          <legend className="px-1 text-sm font-semibold text-foreground">
            Story fields supported by each selected claim
          </legend>
          {storyFields.map((field) => (
            <CheckboxField
              aria-label={`Use ${field.label} in selected claim mappings`}
              defaultChecked
              id={`story-field-${field.value}`}
              key={field.value}
              label={`${field.label} support`}
              name="fieldName"
              value={field.value}
            />
          ))}
        </fieldset>
        <Button disabled={busy} type="submit">
          <ShieldCheck aria-hidden="true" className="size-4" />
          {busy ? "Saving story…" : "Save grounded story"}
        </Button>
      </form>
    </Card>
  );
}

function SessionCreateForm({
  busy,
  onSubmit,
}: {
  busy: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <Card className="p-4 sm:p-5">
      <form className="grid gap-4 sm:grid-cols-2" onSubmit={onSubmit}>
        <LabeledInput
          id="session-title"
          label="Session title"
          name="title"
          required
        />
        <label className="space-y-2 text-sm font-semibold text-foreground">
          Session type
          <Select defaultValue="behavioral" name="kind">
            {sessionKinds.map((kind) => (
              <option key={kind} value={kind}>
                {humanize(kind)}
              </option>
            ))}
          </Select>
        </label>
        <LabeledInput
          id="session-scheduled"
          label="Scheduled time (optional)"
          name="scheduledAt"
          type="datetime-local"
        />
        <div className="flex items-end">
          <Button disabled={busy} type="submit">
            {busy ? "Creating…" : "Create private session"}
          </Button>
        </div>
      </form>
    </Card>
  );
}

function LabeledInput({
  id,
  label,
  ...props
}: React.ComponentProps<typeof Input> & { id: string; label: string }) {
  return (
    <label
      className="space-y-2 text-sm font-semibold text-foreground"
      htmlFor={id}
    >
      {label}
      <Input id={id} {...props} />
    </label>
  );
}

function LabeledTextarea({
  hint,
  id,
  label,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement> & {
  hint?: string;
  id: string;
  label: string;
}) {
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <label
      className="space-y-2 text-sm font-semibold text-foreground"
      htmlFor={id}
    >
      {label}
      <textarea
        aria-describedby={hintId}
        className={fieldClass}
        id={id}
        {...props}
      />
      {hint && (
        <span className="block text-xs font-normal text-muted" id={hintId}>
          {hint}
        </span>
      )}
    </label>
  );
}
