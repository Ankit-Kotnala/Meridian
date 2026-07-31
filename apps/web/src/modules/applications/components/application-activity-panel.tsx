"use client";

import {
  CalendarClock,
  CheckCircle2,
  Circle,
  MessageSquarePlus,
  Plus,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";

import { Alert, Badge, Button, EmptyState, Input, Select } from "@careeros/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  ApiRequestError,
  createApplicationEvent,
  createApplicationNote,
  createApplicationTask,
  listApplicationEvents,
  listApplicationNotes,
  listApplicationTasks,
  updateApplicationTask,
} from "../api/applications-api";
import type {
  ApplicationDetail,
  ApplicationEvent,
  ApplicationEventKind,
  ApplicationNote,
  ApplicationTask,
} from "../api/types";
import { eventKinds, formatDateTime, humanize } from "./application-options";

type NoticeHandlers = {
  onFailure: (message: string, conflict: boolean) => void;
  onSuccess: (message: string) => void;
};

type PageState<T> = {
  error: string | null;
  hasMore: boolean;
  items: T[];
  nextCursor: string | null;
  status: "idle" | "pending" | "success" | "error";
};

function initialPageState<T>(): PageState<T> {
  return {
    error: null,
    hasMore: false,
    items: [],
    nextCursor: null,
    status: "idle",
  };
}

function mergePage<T extends { id: string }>(
  current: T[],
  incoming: T[],
  append: boolean,
): T[] {
  const currentById = new Map(current.map((item) => [item.id, item]));
  if (append) {
    return [
      ...current,
      ...incoming.filter((item) => !currentById.has(item.id)),
    ];
  }
  const incomingIds = new Set(incoming.map((item) => item.id));
  return [
    ...incoming.map((item) => currentById.get(item.id) ?? item),
    ...current.filter((item) => !incomingIds.has(item.id)),
  ];
}

function currentIdempotencyKey(ref: { current: string | undefined }): string {
  ref.current ??= crypto.randomUUID();
  return ref.current;
}

function renewIntent(ref: { current: string | undefined }) {
  ref.current = crypto.randomUUID();
}

export function ApplicationActivityPanel({
  application,
  onFailure,
  onOpenTaskCountChange,
  onSuccess,
  reloadEpoch,
}: {
  application: ApplicationDetail;
  onOpenTaskCountChange: (delta: number) => void;
  reloadEpoch: number;
} & NoticeHandlers) {
  const [tasks, setTasks] =
    useState<PageState<ApplicationTask>>(initialPageState);
  const [notes, setNotes] =
    useState<PageState<ApplicationNote>>(initialPageState);
  const [events, setEvents] =
    useState<PageState<ApplicationEvent>>(initialPageState);
  const [busyKey, setBusyKey] = useState<string>();
  const taskRequest = useRef(0);
  const noteRequest = useRef(0);
  const eventRequest = useRef(0);
  const taskIdempotencyKey = useRef<string | undefined>(undefined);
  const noteIdempotencyKey = useRef<string | undefined>(undefined);
  const eventIdempotencyKey = useRef<string | undefined>(undefined);

  const loadTasks = useCallback(
    async (cursor?: string) => {
      const requestId = ++taskRequest.current;
      setTasks((current) => ({
        ...current,
        error: null,
        status: "pending",
      }));
      try {
        const page = await listApplicationTasks(application.id, {
          ...(cursor ? { cursor } : {}),
          limit: 25,
        });
        if (requestId !== taskRequest.current) return;
        setTasks((current) => ({
          error: null,
          hasMore: page.page.hasMore,
          items: mergePage(current.items, page.data, Boolean(cursor)),
          nextCursor: page.page.nextCursor,
          status: "success",
        }));
      } catch (error) {
        if (requestId !== taskRequest.current) return;
        setTasks((current) => ({
          ...current,
          error: requestErrorMessage(error, "Tasks could not be loaded."),
          status: "error",
        }));
      }
    },
    [application.id],
  );

  const loadNotes = useCallback(
    async (cursor?: string) => {
      const requestId = ++noteRequest.current;
      setNotes((current) => ({
        ...current,
        error: null,
        status: "pending",
      }));
      try {
        const page = await listApplicationNotes(application.id, {
          ...(cursor ? { cursor } : {}),
          limit: 25,
        });
        if (requestId !== noteRequest.current) return;
        setNotes((current) => ({
          error: null,
          hasMore: page.page.hasMore,
          items: mergePage(current.items, page.data, Boolean(cursor)),
          nextCursor: page.page.nextCursor,
          status: "success",
        }));
      } catch (error) {
        if (requestId !== noteRequest.current) return;
        setNotes((current) => ({
          ...current,
          error: requestErrorMessage(error, "Notes could not be loaded."),
          status: "error",
        }));
      }
    },
    [application.id],
  );

  const loadEvents = useCallback(
    async (cursor?: string) => {
      const requestId = ++eventRequest.current;
      setEvents((current) => ({
        ...current,
        error: null,
        status: "pending",
      }));
      try {
        const page = await listApplicationEvents(application.id, {
          ...(cursor ? { cursor } : {}),
          limit: 50,
        });
        if (requestId !== eventRequest.current) return;
        setEvents((current) => ({
          error: null,
          hasMore: page.page.hasMore,
          items: mergePage(current.items, page.data, Boolean(cursor)),
          nextCursor: page.page.nextCursor,
          status: "success",
        }));
      } catch (error) {
        if (requestId !== eventRequest.current) return;
        setEvents((current) => ({
          ...current,
          error: requestErrorMessage(
            error,
            "Timeline events could not be loaded.",
          ),
          status: "error",
        }));
      }
    },
    [application.id],
  );

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (!active) return;
      setTasks(initialPageState());
      setNotes(initialPageState());
      setEvents(initialPageState());
      void loadTasks();
      void loadNotes();
      void loadEvents();
    });
    return () => {
      active = false;
      taskRequest.current += 1;
      noteRequest.current += 1;
      eventRequest.current += 1;
    };
  }, [loadEvents, loadNotes, loadTasks, reloadEpoch]);

  function report(error: unknown, fallback: string) {
    const conflict =
      error instanceof ApiRequestError &&
      (error.failure.status === 409 || error.failure.status === 412);
    onFailure(
      conflict
        ? "This item changed in another session. Reload before trying again."
        : requestErrorMessage(error, fallback),
      conflict,
    );
  }

  async function addTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusyKey("create-task");
    try {
      const task = await createApplicationTask(
        application.id,
        {
          dueAt: String(form.get("dueAt") ?? "") || null,
          title: String(form.get("title") ?? "").trim(),
        },
        currentIdempotencyKey(taskIdempotencyKey),
      );
      setTasks((current) => ({
        ...current,
        items: mergePage(current.items, [task], true),
      }));
      if (!task.completedAt) {
        onOpenTaskCountChange(1);
      }
      renewIntent(taskIdempotencyKey);
      formElement.reset();
      onSuccess("Task added.");
    } catch (error) {
      report(error, "The task could not be added.");
    } finally {
      setBusyKey(undefined);
    }
  }

  async function saveTask(
    task: ApplicationTask,
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusyKey(`task-${task.id}`);
    try {
      const updated = await updateApplicationTask(application.id, task, {
        dueAt: String(form.get("dueAt") ?? "") || null,
        title: String(form.get("title") ?? "").trim(),
      });
      setTasks((current) => ({
        ...current,
        items: current.items.map((item) =>
          item.id === updated.id ? updated : item,
        ),
      }));
      onSuccess("Task updated.");
    } catch (error) {
      report(error, "The task could not be updated.");
    } finally {
      setBusyKey(undefined);
    }
  }

  async function toggleTask(task: ApplicationTask) {
    setBusyKey(`task-${task.id}`);
    try {
      const updated = await updateApplicationTask(application.id, task, {
        completed: !task.completedAt,
      });
      setTasks((current) => ({
        ...current,
        items: current.items.map((item) =>
          item.id === updated.id ? updated : item,
        ),
      }));
      if (Boolean(task.completedAt) !== Boolean(updated.completedAt)) {
        onOpenTaskCountChange(updated.completedAt ? -1 : 1);
      }
      onSuccess(updated.completedAt ? "Task completed." : "Task reopened.");
    } catch (error) {
      report(error, "The task status could not be updated.");
    } finally {
      setBusyKey(undefined);
    }
  }

  async function addNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusyKey("create-note");
    try {
      const note = await createApplicationNote(
        application.id,
        {
          body: String(form.get("body") ?? "").trim(),
        },
        currentIdempotencyKey(noteIdempotencyKey),
      );
      setNotes((current) => ({
        ...current,
        items: [note, ...current.items.filter((item) => item.id !== note.id)],
      }));
      renewIntent(noteIdempotencyKey);
      formElement.reset();
      onSuccess("Note added.");
    } catch (error) {
      report(error, "The note could not be added.");
    } finally {
      setBusyKey(undefined);
    }
  }

  async function addEvent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const occurredAt = String(form.get("occurredAt") ?? "");
    setBusyKey("create-event");
    try {
      const created = await createApplicationEvent(
        application.id,
        {
          description: String(form.get("description") ?? "").trim() || null,
          eventKind: String(form.get("eventKind")) as ApplicationEventKind,
          metadata: {},
          occurredAt: occurredAt ? new Date(occurredAt).toISOString() : null,
          title: String(form.get("title") ?? "").trim(),
        },
        currentIdempotencyKey(eventIdempotencyKey),
      );
      setEvents((current) => ({
        ...current,
        items: [
          created,
          ...current.items.filter((item) => item.id !== created.id),
        ],
      }));
      renewIntent(eventIdempotencyKey);
      formElement.reset();
      onSuccess("Timeline event recorded.");
    } catch (error) {
      report(error, "The event could not be recorded.");
    } finally {
      setBusyKey(undefined);
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <section
        aria-labelledby="application-tasks-heading"
        className="rounded-xl border border-line bg-surface p-4 shadow-sm sm:p-5"
      >
        <div className="flex items-center gap-2">
          <CalendarClock aria-hidden="true" className="size-5 text-primary" />
          <h2
            className="text-lg font-black text-foreground"
            id="application-tasks-heading"
          >
            Tasks
          </h2>
        </div>
        <form
          className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_10rem_auto]"
          onChange={() => renewIntent(taskIdempotencyKey)}
          onSubmit={(event) => void addTask(event)}
        >
          <label className="text-sm font-bold text-foreground">
            Task
            <Input className="mt-1" maxLength={200} name="title" required />
          </label>
          <label className="text-sm font-bold text-foreground">
            Due date
            <Input className="mt-1" name="dueAt" type="date" />
          </label>
          <Button
            className="self-end"
            loading={busyKey === "create-task"}
            type="submit"
          >
            <Plus aria-hidden="true" className="size-4" />
            Add
          </Button>
        </form>

        {tasks.status === "pending" && tasks.items.length === 0 && (
          <p className="mt-5 text-sm text-muted" role="status">
            Loading tasks...
          </p>
        )}
        {tasks.error && (
          <Alert className="mt-5" title="Tasks unavailable" tone="danger">
            <p>{tasks.error}</p>
            <Button
              className="mt-3 min-h-9 px-3"
              onClick={() =>
                void loadTasks(
                  tasks.items.length
                    ? (tasks.nextCursor ?? undefined)
                    : undefined,
                )
              }
              variant="secondary"
            >
              Retry tasks
            </Button>
          </Alert>
        )}
        {tasks.items.length ? (
          <ul className="mt-5 space-y-3">
            {tasks.items.map((task) => (
              <li className="rounded-xl border border-line p-3" key={task.id}>
                <div className="flex items-start gap-3">
                  <button
                    aria-label={
                      task.completedAt
                        ? `Reopen ${task.title}`
                        : `Complete ${task.title}`
                    }
                    className="mt-1 shrink-0 rounded-full text-primary focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary-soft"
                    disabled={busyKey === `task-${task.id}`}
                    onClick={() => void toggleTask(task)}
                    type="button"
                  >
                    {task.completedAt ? (
                      <CheckCircle2 aria-hidden="true" className="size-5" />
                    ) : (
                      <Circle aria-hidden="true" className="size-5" />
                    )}
                  </button>
                  <form
                    className="min-w-0 flex-1"
                    onSubmit={(event) => void saveTask(task, event)}
                  >
                    <fieldset className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_9rem_auto]">
                      <legend className="sr-only">
                        Edit task: {task.title}
                      </legend>
                      <label
                        className="sr-only"
                        htmlFor={`task-title-${task.id}`}
                      >
                        Task title
                      </label>
                      <Input
                        className={task.completedAt ? "line-through" : ""}
                        defaultValue={task.title}
                        id={`task-title-${task.id}`}
                        maxLength={200}
                        name="title"
                        required
                      />
                      <label
                        className="sr-only"
                        htmlFor={`task-due-${task.id}`}
                      >
                        Task due date
                      </label>
                      <Input
                        defaultValue={task.dueAt ?? ""}
                        id={`task-due-${task.id}`}
                        name="dueAt"
                        type="date"
                      />
                      <Button
                        className="min-h-9 self-center px-3"
                        loading={busyKey === `task-${task.id}`}
                        type="submit"
                        variant="secondary"
                      >
                        Save
                      </Button>
                    </fieldset>
                  </form>
                </div>
              </li>
            ))}
          </ul>
        ) : tasks.status === "success" ? (
          <p className="mt-5 text-sm text-muted">
            No tasks yet. Add a follow-up, preparation, or interview task.
          </p>
        ) : null}
        {tasks.hasMore && (
          <Button
            className="mt-4"
            disabled={!tasks.nextCursor}
            loading={tasks.status === "pending"}
            onClick={() => void loadTasks(tasks.nextCursor ?? undefined)}
            variant="secondary"
          >
            Load more tasks
          </Button>
        )}
      </section>

      <section
        aria-labelledby="application-notes-heading"
        className="rounded-xl border border-line bg-surface p-4 shadow-sm sm:p-5"
      >
        <div className="flex items-center gap-2">
          <MessageSquarePlus
            aria-hidden="true"
            className="size-5 text-primary"
          />
          <h2
            className="text-lg font-black text-foreground"
            id="application-notes-heading"
          >
            Notes
          </h2>
        </div>
        <form
          className="mt-4"
          onChange={() => renewIntent(noteIdempotencyKey)}
          onSubmit={(event) => void addNote(event)}
        >
          <label className="text-sm font-bold text-foreground">
            Add a private application note
            <textarea
              className="mt-1 min-h-28 w-full resize-y rounded-xl border border-line bg-surface px-3.5 py-3 text-sm text-foreground shadow-sm outline-none focus:border-primary focus:ring-3 focus:ring-primary-soft"
              maxLength={2000}
              name="body"
              required
            />
          </label>
          <Button
            className="mt-3"
            loading={busyKey === "create-note"}
            type="submit"
          >
            Add note
          </Button>
        </form>
        {notes.status === "pending" && notes.items.length === 0 && (
          <p className="mt-5 text-sm text-muted" role="status">
            Loading notes...
          </p>
        )}
        {notes.error && (
          <Alert className="mt-5" title="Notes unavailable" tone="danger">
            <p>{notes.error}</p>
            <Button
              className="mt-3 min-h-9 px-3"
              onClick={() =>
                void loadNotes(
                  notes.items.length
                    ? (notes.nextCursor ?? undefined)
                    : undefined,
                )
              }
              variant="secondary"
            >
              Retry notes
            </Button>
          </Alert>
        )}
        {notes.items.length ? (
          <ul className="mt-5 space-y-3">
            {notes.items.map((note) => (
              <li className="rounded-xl bg-surface-subtle p-3" key={note.id}>
                <p className="whitespace-pre-wrap text-sm text-foreground">
                  {note.body}
                </p>
                <p className="mt-2 text-xs text-muted">
                  {formatDateTime(note.createdAt)}
                </p>
              </li>
            ))}
          </ul>
        ) : notes.status === "success" ? (
          <p className="mt-5 text-sm text-muted">No notes recorded.</p>
        ) : null}
        {notes.hasMore && (
          <Button
            className="mt-4"
            disabled={!notes.nextCursor}
            loading={notes.status === "pending"}
            onClick={() => void loadNotes(notes.nextCursor ?? undefined)}
            variant="secondary"
          >
            Load more notes
          </Button>
        )}
      </section>

      <section
        aria-labelledby="application-event-form-heading"
        className="rounded-xl border border-line bg-surface p-4 shadow-sm sm:p-5"
      >
        <h2
          className="text-lg font-black text-foreground"
          id="application-event-form-heading"
        >
          Record an event
        </h2>
        <form
          className="mt-4 grid gap-3 sm:grid-cols-2"
          onChange={() => renewIntent(eventIdempotencyKey)}
          onSubmit={(event) => void addEvent(event)}
        >
          <label className="text-sm font-bold text-foreground">
            Event type
            <Select className="mt-1" name="eventKind">
              {eventKinds.map((kind) => (
                <option key={kind} value={kind}>
                  {humanize(kind)}
                </option>
              ))}
            </Select>
          </label>
          <label className="text-sm font-bold text-foreground">
            Occurred at
            <Input className="mt-1" name="occurredAt" type="datetime-local" />
          </label>
          <label className="text-sm font-bold text-foreground sm:col-span-2">
            Title
            <Input className="mt-1" maxLength={200} name="title" required />
          </label>
          <label className="text-sm font-bold text-foreground sm:col-span-2">
            Description
            <textarea
              className="mt-1 min-h-24 w-full resize-y rounded-xl border border-line bg-surface px-3.5 py-3 text-sm text-foreground shadow-sm outline-none focus:border-primary focus:ring-3 focus:ring-primary-soft"
              maxLength={1000}
              name="description"
            />
          </label>
          <div className="sm:col-span-2">
            <Button loading={busyKey === "create-event"} type="submit">
              Record event
            </Button>
          </div>
        </form>
      </section>

      <section
        aria-labelledby="application-timeline-heading"
        className="rounded-xl border border-line bg-surface p-4 shadow-sm sm:p-5"
      >
        <h2
          className="text-lg font-black text-foreground"
          id="application-timeline-heading"
        >
          Timeline
        </h2>
        {events.status === "pending" && events.items.length === 0 && (
          <p className="mt-5 text-sm text-muted" role="status">
            Loading timeline...
          </p>
        )}
        {events.error && (
          <Alert className="mt-5" title="Timeline unavailable" tone="danger">
            <p>{events.error}</p>
            <Button
              className="mt-3 min-h-9 px-3"
              onClick={() =>
                void loadEvents(
                  events.items.length
                    ? (events.nextCursor ?? undefined)
                    : undefined,
                )
              }
              variant="secondary"
            >
              Retry timeline
            </Button>
          </Alert>
        )}
        {events.items.length ? (
          <ol className="relative mt-5 space-y-5 border-l border-line pl-5">
            {[...events.items]
              .sort((left, right) =>
                right.occurredAt.localeCompare(left.occurredAt),
              )
              .map((event) => (
                <li key={event.id}>
                  <span
                    aria-hidden="true"
                    className="absolute -left-1.5 mt-1.5 size-3 rounded-full border-2 border-white bg-primary"
                  />
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-black text-foreground">
                      {event.title}
                    </h3>
                    <Badge tone="neutral">{humanize(event.eventKind)}</Badge>
                  </div>
                  {event.description && (
                    <p className="mt-1 whitespace-pre-wrap text-sm text-muted">
                      {event.description}
                    </p>
                  )}
                  <p className="mt-1 text-xs text-muted">
                    {formatDateTime(event.occurredAt)}
                  </p>
                </li>
              ))}
          </ol>
        ) : events.status === "success" ? (
          <EmptyState
            className="mt-4 min-h-48"
            description="Stage changes, task activity, pack generation, and your custom events appear here."
            title="No timeline events"
          />
        ) : null}
        {events.hasMore && (
          <Button
            className="mt-4"
            disabled={!events.nextCursor}
            loading={events.status === "pending"}
            onClick={() => void loadEvents(events.nextCursor ?? undefined)}
            variant="secondary"
          >
            Load more timeline events
          </Button>
        )}
      </section>
    </div>
  );
}
