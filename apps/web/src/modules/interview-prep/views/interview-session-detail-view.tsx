"use client";

import {
  ArrowLeft,
  RefreshCcw,
  Save,
  ShieldCheck,
  Sparkles,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";

import {
  Alert,
  Badge,
  Button,
  CheckboxField,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Input,
  LoadingSkeleton,
  Select,
  Tabs,
  buttonStyles,
} from "@careeros/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  ApiRequestError,
  createQuestion,
  createSessionNote,
  deleteSession,
  deleteSessionNote,
  generateFollowUpDraft,
  generateQuestionBank,
  getSession,
  listFollowUpDrafts,
  listQuestions,
  listSessionNotes,
  updateSession,
  updateSessionNote,
} from "../api/interview-prep-api";
import type {
  FollowUpDraft,
  FollowUpDraftSummary,
  InterviewQuestion,
  InterviewQuestionCreateInput,
  InterviewSession,
  InterviewSessionKind,
  InterviewQuestionSummary,
  SessionNote,
  SessionNoteInput,
} from "../api/types";
import { useIntentActivity } from "../state/use-intent-activity";

const sessionKinds: readonly InterviewSessionKind[] = [
  "recruiter_screen",
  "behavioral",
  "technical",
  "hiring_manager",
  "panel",
  "other",
];
const questionKinds: readonly InterviewQuestionCreateInput["kind"][] = [
  "behavioral",
  "role_specific",
  "technical",
  "company",
  "follow_up",
  "custom",
];

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

function localDateTime(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function questionSummary(
  question: InterviewQuestion,
): InterviewQuestionSummary {
  return {
    createdAt: question.createdAt,
    generated: question.generated,
    groundingStatus: question.groundingStatus,
    groundingWarning: question.groundingWarning,
    id: question.id,
    kind: question.kind,
    ordinal: question.ordinal,
    prompt: question.prompt,
    sessionId: question.sessionId,
    sourceClaimCount: question.sourceClaimIds.length,
    sourceRequirementCount: question.sourceRequirementIds.length,
  };
}

function draftSummary(draft: FollowUpDraft): FollowUpDraftSummary {
  return {
    body: draft.body,
    contentSha256: draft.contentSha256,
    createdAt: draft.createdAt,
    groundingStatus: draft.groundingStatus,
    groundingWarning: draft.groundingWarning,
    id: draft.id,
    sessionId: draft.sessionId,
    sourceClaimCount: draft.sourceClaims.length,
    subject: draft.subject,
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

type SessionState =
  | { status: "loading" }
  | {
      drafts: FollowUpDraftSummary[];
      draftCursor: string | null;
      notes: SessionNote[];
      noteCursor: string | null;
      questions: InterviewQuestionSummary[];
      questionCursor: string | null;
      session: InterviewSession;
      status: "ready";
    }
  | { message: string; status: "error" };

export function InterviewSessionDetailView({
  sessionId,
}: {
  sessionId: string;
}) {
  const router = useRouter();
  const [state, setState] = useState<SessionState>({ status: "loading" });
  const [failure, setFailure] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const {
    begin: beginIntentActivity,
    end: endIntentActivity,
    isActive: isIntentActive,
  } = useIntentActivity();
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("context");
  const requestEpoch = useRef(0);
  const controller = useRef<AbortController | null>(null);
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

  const load = useCallback(
    async (conflictMessage?: string) => {
      controller.current?.abort();
      const nextController = new AbortController();
      controller.current = nextController;
      const epoch = ++requestEpoch.current;
      setFailure(undefined);
      try {
        const [session, questions, notes, drafts] = await Promise.all([
          getSession(sessionId, nextController.signal),
          listQuestions(sessionId, {
            limit: 50,
            signal: nextController.signal,
          }),
          listSessionNotes(sessionId, {
            limit: 50,
            signal: nextController.signal,
          }),
          listFollowUpDrafts(sessionId, {
            limit: 50,
            signal: nextController.signal,
          }),
        ]);
        if (epoch !== requestEpoch.current || nextController.signal.aborted)
          return;
        setState({
          drafts: drafts.data,
          draftCursor: drafts.page.nextCursor,
          notes: notes.data,
          noteCursor: notes.page.nextCursor,
          questions: questions.data,
          questionCursor: questions.page.nextCursor,
          session,
          status: "ready",
        });
        if (conflictMessage) setFailure(conflictMessage);
      } catch (error) {
        if (epoch !== requestEpoch.current || nextController.signal.aborted)
          return;
        setState({
          message: requestErrorMessage(
            error,
            "The interview session could not be loaded.",
          ),
          status: "error",
        });
      }
    },
    [sessionId],
  );

  useEffect(() => {
    queueMicrotask(() => void load());
    return () => {
      controller.current?.abort();
      requestEpoch.current += 1;
    };
  }, [load]);

  async function loadMore(kind: "questions" | "notes" | "drafts") {
    if (state.status !== "ready") return;
    const cursor =
      kind === "questions"
        ? state.questionCursor
        : kind === "notes"
          ? state.noteCursor
          : state.draftCursor;
    if (!cursor) return;
    const epoch = requestEpoch.current;
    const activity = beginIntentActivity(`more-${kind}`);
    setFailure(undefined);
    try {
      if (kind === "questions") {
        const page = await listQuestions(sessionId, { cursor, limit: 50 });
        if (epoch !== requestEpoch.current) return;
        setState((current) =>
          current.status === "ready" && current.questionCursor === cursor
            ? {
                ...current,
                questions: mergeById(current.questions, page.data),
                questionCursor: page.page.nextCursor,
              }
            : current,
        );
      } else if (kind === "notes") {
        const page = await listSessionNotes(sessionId, { cursor, limit: 50 });
        if (epoch !== requestEpoch.current) return;
        setState((current) =>
          current.status === "ready" && current.noteCursor === cursor
            ? {
                ...current,
                notes: mergeById(current.notes, page.data),
                noteCursor: page.page.nextCursor,
              }
            : current,
        );
      } else {
        const page = await listFollowUpDrafts(sessionId, {
          cursor,
          limit: 50,
        });
        if (epoch !== requestEpoch.current) return;
        setState((current) =>
          current.status === "ready" && current.draftCursor === cursor
            ? {
                ...current,
                drafts: mergeById(current.drafts, page.data),
                draftCursor: page.page.nextCursor,
              }
            : current,
        );
      }
    } catch (error) {
      if (epoch !== requestEpoch.current) return;
      setFailure(
        requestErrorMessage(error, `More ${kind} could not be loaded.`),
      );
    } finally {
      endIntentActivity(activity);
    }
  }

  async function saveSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state.status !== "ready") return;
    const form = new FormData(event.currentTarget);
    const scheduledAt = String(form.get("scheduledAt") ?? "");
    const activity = beginIntentActivity("session");
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const session = await updateSession(state.session, {
        kind: String(form.get("kind")) as InterviewSessionKind,
        scheduledAt: scheduledAt ? new Date(scheduledAt).toISOString() : null,
        title: String(form.get("title") ?? "").trim(),
      });
      setState((current) =>
        current.status === "ready" ? { ...current, session } : current,
      );
      setSuccess("Session details updated.");
    } catch (error) {
      await handleConflict(
        error,
        "The session could not be updated.",
        "This session changed elsewhere. The authoritative session and private collections were reloaded.",
      );
    } finally {
      endIntentActivity(activity);
    }
  }

  async function addQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state.status !== "ready") return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const input = {
      kind: String(form.get("kind")) as InterviewQuestionCreateInput["kind"],
      prompt: String(form.get("prompt") ?? "").trim(),
      sourceClaimIds: form.getAll("sourceClaimId").map(String),
      sourceRequirementIds: form.getAll("sourceRequirementId").map(String),
    };
    const intent = `question:${JSON.stringify(input)}`;
    const activity = beginIntentActivity("question");
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const question = await createQuestion(
        sessionId,
        input,
        stableIntent(intent),
      );
      clearIntent(intent);
      setState((current) => {
        if (current.status !== "ready") return current;
        const exists = current.questions.some(
          (item) => item.id === question.id,
        );
        return {
          ...current,
          questions: [
            questionSummary(question),
            ...current.questions.filter((item) => item.id !== question.id),
          ],
          session: {
            ...current.session,
            questionCount: current.session.questionCount + (exists ? 0 : 1),
          },
        };
      });
      setSuccess("Private practice question added.");
      formElement.reset();
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "The practice question could not be added."),
      );
    } finally {
      endIntentActivity(activity);
    }
  }

  async function generateQuestions() {
    if (state.status !== "ready") return;
    const intent = `question-bank:${state.session.context.snapshotSha256}`;
    const activity = beginIntentActivity("generate-questions");
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const result = await generateQuestionBank(
        sessionId,
        stableIntent(intent),
      );
      clearIntent(intent);
      setState((current) => {
        if (current.status !== "ready") return current;
        const newCount = result.data.filter(
          (item) =>
            !current.questions.some((existing) => existing.id === item.id),
        ).length;
        return {
          ...current,
          questions: [
            ...result.data.map(questionSummary),
            ...current.questions.filter(
              (existing) =>
                !result.data.some((item) => item.id === existing.id),
            ),
          ],
          session: {
            ...current.session,
            questionBankGenerated: true,
            questionBankId: current.session.id,
            questionCount: current.session.questionCount + newCount,
          },
        };
      });
      setSuccess(
        `${result.data.length} grounded questions generated from the immutable session context.`,
      );
    } catch (error) {
      setFailure(
        requestErrorMessage(
          error,
          "The grounded question bank could not be generated.",
        ),
      );
    } finally {
      endIntentActivity(activity);
    }
  }

  async function addNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const input: SessionNoteInput = {
      body: String(form.get("body") ?? "").trim(),
      kind: String(form.get("kind")) as SessionNoteInput["kind"],
    };
    const intent = `note:${JSON.stringify(input)}`;
    const activity = beginIntentActivity("note");
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const note = await createSessionNote(
        sessionId,
        input,
        stableIntent(intent),
      );
      clearIntent(intent);
      setState((current) =>
        current.status === "ready"
          ? {
              ...current,
              notes: [note, ...current.notes],
              session: {
                ...current.session,
                noteCount: current.session.noteCount + 1,
              },
            }
          : current,
      );
      setSuccess("Private note saved.");
      formElement.reset();
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "The private note could not be saved."),
      );
    } finally {
      endIntentActivity(activity);
    }
  }

  async function saveNote(
    note: SessionNote,
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const activity = beginIntentActivity(`note-${note.id}`);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const updated = await updateSessionNote(sessionId, note, {
        body: String(form.get("body") ?? "").trim(),
        kind: String(form.get("kind")) as SessionNoteInput["kind"],
      });
      setState((current) =>
        current.status === "ready"
          ? {
              ...current,
              notes: current.notes.map((item) =>
                item.id === updated.id ? updated : item,
              ),
            }
          : current,
      );
      setSuccess("Private note updated.");
    } catch (error) {
      await handleConflict(
        error,
        "The note could not be updated.",
        "A private note changed elsewhere. The authoritative session and notes were reloaded.",
      );
    } finally {
      endIntentActivity(activity);
    }
  }

  async function removeNote(note: SessionNote) {
    const activity = beginIntentActivity(`note-${note.id}`);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      await deleteSessionNote(sessionId, note);
      setState((current) =>
        current.status === "ready"
          ? {
              ...current,
              notes: current.notes.filter((item) => item.id !== note.id),
              session: {
                ...current.session,
                noteCount: Math.max(0, current.session.noteCount - 1),
              },
            }
          : current,
      );
      setSuccess("Private note deleted.");
    } catch (error) {
      await handleConflict(
        error,
        "The note could not be deleted.",
        "A private note changed elsewhere. The authoritative session and notes were reloaded.",
      );
    } finally {
      endIntentActivity(activity);
    }
  }

  async function createDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state.status !== "ready") return;
    const sourceClaimIds = new FormData(event.currentTarget)
      .getAll("draftClaimId")
      .map(String);
    if (sourceClaimIds.length === 0) {
      setFailure("Choose at least one grounded claim for the follow-up draft.");
      return;
    }
    const input = { sourceClaimIds };
    const intent = `follow-up:${JSON.stringify(input)}`;
    const activity = beginIntentActivity("draft");
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const draft = await generateFollowUpDraft(
        sessionId,
        input,
        stableIntent(intent),
      );
      clearIntent(intent);
      setState((current) =>
        current.status === "ready"
          ? {
              ...current,
              drafts: [
                draftSummary(draft),
                ...current.drafts.filter((item) => item.id !== draft.id),
              ],
              session: {
                ...current.session,
                followUpDraftCount: current.session.followUpDraftCount + 1,
              },
            }
          : current,
      );
      setSuccess(
        "A grounded draft was created for your review. CareerOS did not send it.",
      );
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "The follow-up draft could not be created."),
      );
    } finally {
      endIntentActivity(activity);
    }
  }

  async function removeSession() {
    if (state.status !== "ready") return;
    const activity = beginIntentActivity("delete");
    setFailure(undefined);
    try {
      await deleteSession(state.session);
      router.replace("/interview-prep");
      router.refresh();
    } catch (error) {
      const stale =
        error instanceof ApiRequestError &&
        (error.failure.status === 409 || error.failure.status === 412);
      setDeleteOpen(false);
      if (stale) {
        await load(
          "This session changed elsewhere. The authoritative version was reloaded and was not deleted.",
        );
      } else {
        setFailure(
          requestErrorMessage(error, "The session could not be deleted."),
        );
      }
    } finally {
      endIntentActivity(activity);
    }
  }

  async function handleConflict(
    error: unknown,
    fallback: string,
    conflict: string,
  ) {
    const stale =
      error instanceof ApiRequestError &&
      (error.failure.status === 409 || error.failure.status === 412);
    if (stale) await load(conflict);
    else setFailure(requestErrorMessage(error, fallback));
  }

  if (state.status === "error") {
    return (
      <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
        <ErrorState
          description={state.message}
          onRetry={() => void load()}
          title="Interview session unavailable"
        />
      </main>
    );
  }

  if (state.status === "loading") {
    return (
      <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
        <LoadingSkeleton />
      </main>
    );
  }

  const { session } = state;

  return (
    <main
      className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8"
      id="main-content"
    >
      <Link
        className={`${buttonStyles.base} ${buttonStyles.ghost} -ml-3`}
        href="/interview-prep"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        Interview Prep
      </Link>

      <header className="rounded-xl border border-line bg-white p-4 shadow-sm sm:p-5">
        <div className="flex flex-wrap gap-2">
          <Badge tone="primary">{humanize(session.kind)}</Badge>
          <Badge tone="neutral">{dateTime(session.scheduledAt)}</Badge>
          <Badge tone="success">Private workspace</Badge>
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
        </div>
        <h1 className="mt-3 text-2xl font-black text-foreground">
          {session.title}
        </h1>
        <p className="mt-1 text-sm text-muted">
          {session.context.jobTitle}
          {session.context.company ? ` at ${session.context.company}` : ""}
        </p>
        <p className="mt-3 text-xs font-semibold text-muted">
          Resume version {session.context.resumeVersionNumber} · Job version{" "}
          {session.context.jobVersion} · Snapshot{" "}
          <code className="break-all">{session.context.snapshotSha256}</code>
        </p>
      </header>

      {session.groundingStatus !== "current" && (
        <Alert title="Grounding review required" tone="warning">
          {session.groundingWarning ??
            "Current evidence eligibility could not be confirmed. Review the source evidence before using generated material."}
        </Alert>
      )}

      {failure && (
        <Alert title="Review current data" tone="danger">
          <p>{failure}</p>
          <Button
            className="mt-3 min-h-9 px-3"
            onClick={() => void load()}
            variant="secondary"
          >
            <RefreshCcw aria-hidden="true" className="size-4" />
            Reload authoritative data
          </Button>
        </Alert>
      )}
      {success && (
        <Alert title="Session updated" tone="success">
          {success}
        </Alert>
      )}

      <Tabs
        label="Interview session workspace"
        onValueChange={setActiveTab}
        tabs={[
          {
            id: "context",
            label: "Grounded context",
            panel: (
              <ContextPanel
                session={session}
                onDelete={() => setDeleteOpen(true)}
                onSubmit={saveSession}
                saving={isIntentActive("session")}
              />
            ),
          },
          {
            id: "questions",
            label: `Questions (${session.questionCount})`,
            panel: (
              <QuestionsPanel
                isBusy={isIntentActive}
                onGenerate={() => void generateQuestions()}
                onLoadMore={() => void loadMore("questions")}
                onSubmit={addQuestion}
                questionCursor={state.questionCursor}
                questions={state.questions}
                session={session}
              />
            ),
          },
          {
            id: "notes",
            label: `Private notes (${session.noteCount})`,
            panel: (
              <NotesPanel
                isBusy={isIntentActive}
                noteCursor={state.noteCursor}
                notes={state.notes}
                onCreate={addNote}
                onDelete={(note) => void removeNote(note)}
                onLoadMore={() => void loadMore("notes")}
                onSave={(note, event) => void saveNote(note, event)}
              />
            ),
          },
          {
            id: "follow-up",
            label: `Follow-up drafts (${session.followUpDraftCount})`,
            panel: (
              <DraftsPanel
                busy={isIntentActive("draft")}
                draftCursor={state.draftCursor}
                drafts={state.drafts}
                onLoadMore={() => void loadMore("drafts")}
                onSubmit={createDraft}
                session={session}
              />
            ),
          },
        ]}
        value={activeTab}
      />

      <ConfirmDialog
        confirmLabel="Delete session"
        description="This removes the private session, questions, notes, and review drafts. It does not alter the source application, claims, or Career Record evidence."
        loading={isIntentActive("delete")}
        onConfirm={() => void removeSession()}
        onOpenChange={setDeleteOpen}
        open={deleteOpen}
        title="Delete this interview session?"
      />
    </main>
  );
}

function ContextPanel({
  onDelete,
  onSubmit,
  saving,
  session,
}: {
  onDelete: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  saving: boolean;
  session: InterviewSession;
}) {
  return (
    <div className="space-y-6 pt-5">
      <form
        className="grid gap-4 rounded-xl border border-line bg-white p-4 sm:grid-cols-2 sm:p-5"
        key={session.version}
        onSubmit={onSubmit}
      >
        <SessionInput
          defaultValue={session.title}
          id="session-detail-title"
          label="Session title"
          name="title"
          required
        />
        <label className="space-y-2 text-sm font-bold text-foreground">
          Session type
          <Select defaultValue={session.kind} name="kind">
            {sessionKinds.map((kind) => (
              <option key={kind} value={kind}>
                {humanize(kind)}
              </option>
            ))}
          </Select>
        </label>
        <SessionInput
          defaultValue={localDateTime(session.scheduledAt)}
          id="session-detail-scheduled"
          label="Scheduled time"
          name="scheduledAt"
          type="datetime-local"
        />
        <div className="flex items-end gap-2">
          <Button disabled={saving} type="submit">
            <Save aria-hidden="true" className="size-4" />
            {saving ? "Saving…" : "Save details"}
          </Button>
          <Button onClick={onDelete} type="button" variant="danger">
            <Trash2 aria-hidden="true" className="size-4" />
            Delete
          </Button>
        </div>
      </form>

      <section aria-labelledby="session-claims" className="space-y-3">
        <h2 className="text-lg font-black text-foreground" id="session-claims">
          Immutable claim context
        </h2>
        {session.context.claims.length === 0 ? (
          <EmptyState
            description="No eligible claims were available when this session snapshot was created."
            title="No claim context"
          />
        ) : (
          <ul className="grid gap-3 lg:grid-cols-2">
            {session.context.claims.map((claim) => (
              <li
                className="rounded-xl border border-line bg-white p-4"
                key={claim.sourceClaimId}
              >
                <div className="flex flex-wrap gap-2">
                  {claim.strong && <Badge tone="warning">Strong claim</Badge>}
                  <Badge tone="success">
                    {claim.evidencePins.length} evidence{" "}
                    {claim.evidencePins.length === 1 ? "pin" : "pins"}
                  </Badge>
                </div>
                <p className="mt-3 text-sm leading-6 text-foreground">
                  {claim.text}
                </p>
                <p className="mt-2 text-xs text-muted">
                  SHA-256: <code className="break-all">{claim.textSha256}</code>
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="session-requirements" className="space-y-3">
        <h2
          className="text-lg font-black text-foreground"
          id="session-requirements"
        >
          Role requirements
        </h2>
        <ul className="grid gap-3 lg:grid-cols-2">
          {session.context.requirements.map((requirement) => (
            <li
              className="rounded-xl border border-line bg-white p-4"
              key={requirement.requirementId}
            >
              <Badge
                tone={
                  requirement.importance === "mandatory" ? "warning" : "neutral"
                }
              >
                {humanize(requirement.importance)}
              </Badge>
              <p className="mt-3 text-sm leading-6 text-foreground">
                {requirement.text}
              </p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function QuestionsPanel({
  isBusy,
  onGenerate,
  onLoadMore,
  onSubmit,
  questionCursor,
  questions,
  session,
}: {
  isBusy: (key: string) => boolean;
  onGenerate: () => void;
  onLoadMore: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  questionCursor: string | null;
  questions: InterviewQuestionSummary[];
  session: InterviewSession;
}) {
  return (
    <div className="space-y-5 pt-5">
      <Alert title="Grounded question bank" tone="info">
        Generated questions use only the immutable role requirements, claims,
        and evidence snapshot shown in this session.
      </Alert>
      <Button
        disabled={
          isBusy("generate-questions") ||
          session.questionBankGenerated ||
          session.groundingStatus !== "current"
        }
        onClick={onGenerate}
        variant="secondary"
      >
        <Sparkles aria-hidden="true" className="size-4" />
        {isBusy("generate-questions")
          ? "Generating…"
          : session.questionBankGenerated
            ? "Question bank already generated"
            : session.groundingStatus !== "current"
              ? "Review evidence before generating"
              : "Generate grounded questions"}
      </Button>
      <form
        className="space-y-4 rounded-xl border border-line bg-white p-4 sm:p-5"
        onSubmit={onSubmit}
      >
        <h2 className="font-black text-foreground">Add a private question</h2>
        <SessionTextarea
          id="custom-question"
          label="Question prompt"
          maxLength={1000}
          name="prompt"
          required
        />
        <label className="space-y-2 text-sm font-bold text-foreground">
          Question kind
          <Select defaultValue="custom" name="kind">
            {questionKinds.map((kind) => (
              <option key={kind} value={kind}>
                {humanize(kind)}
              </option>
            ))}
          </Select>
        </label>
        <details className="rounded-xl border border-line p-4">
          <summary className="cursor-pointer font-bold text-foreground">
            Link exact claims and requirements
          </summary>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <fieldset className="space-y-2">
              <legend className="font-bold text-foreground">Claims</legend>
              {session.context.claims.map((claim) => (
                <CheckboxField
                  id={`question-claim-${claim.sourceClaimId}`}
                  key={claim.sourceClaimId}
                  label={claim.text}
                  name="sourceClaimId"
                  value={claim.sourceClaimId}
                />
              ))}
            </fieldset>
            <fieldset className="space-y-2">
              <legend className="font-bold text-foreground">
                Requirements
              </legend>
              {session.context.requirements.map((requirement) => (
                <CheckboxField
                  id={`question-requirement-${requirement.requirementId}`}
                  key={requirement.requirementId}
                  label={requirement.text}
                  name="sourceRequirementId"
                  value={requirement.requirementId}
                />
              ))}
            </fieldset>
          </div>
        </details>
        <Button disabled={isBusy("question")} type="submit">
          {isBusy("question") ? "Adding…" : "Add question"}
        </Button>
      </form>
      {questions.length === 0 ? (
        <EmptyState
          description="Generate a grounded bank or add a private custom question."
          title="No practice questions"
        />
      ) : (
        <ol className="space-y-3">
          {questions.map((question) => (
            <li
              className="rounded-xl border border-line bg-white p-4 shadow-sm"
              key={question.id}
            >
              <div className="flex flex-wrap gap-2">
                <Badge tone={question.generated ? "primary" : "neutral"}>
                  {question.generated
                    ? question.groundingStatus === "current"
                      ? "Evidence current"
                      : "Generated · review grounding"
                    : "User authored"}
                </Badge>
                <Badge tone="neutral">{humanize(question.kind)}</Badge>
              </div>
              {question.groundingWarning && (
                <p className="mt-2 text-xs font-semibold text-warning-strong">
                  {question.groundingWarning}
                </p>
              )}
              <p className="mt-3 text-sm font-semibold leading-6 text-foreground">
                {question.prompt}
              </p>
              <p className="mt-2 text-xs text-muted">
                {question.sourceClaimCount} claim links ·{" "}
                {question.sourceRequirementCount} requirement links
              </p>
            </li>
          ))}
        </ol>
      )}
      {questionCursor && (
        <Button
          disabled={isBusy("more-questions")}
          onClick={onLoadMore}
          variant="secondary"
        >
          Load more questions
        </Button>
      )}
    </div>
  );
}

function NotesPanel({
  isBusy,
  noteCursor,
  notes,
  onCreate,
  onDelete,
  onLoadMore,
  onSave,
}: {
  isBusy: (key: string) => boolean;
  noteCursor: string | null;
  notes: SessionNote[];
  onCreate: (event: FormEvent<HTMLFormElement>) => void;
  onDelete: (note: SessionNote) => void;
  onLoadMore: () => void;
  onSave: (note: SessionNote, event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <div className="space-y-5 pt-5">
      <Alert title="Private by design" tone="info">
        Notes and reflections are excluded from question and follow-up
        generation. They are never sent to employers or contacts.
      </Alert>
      <form
        className="space-y-4 rounded-xl border border-line bg-white p-4 sm:p-5"
        onSubmit={onCreate}
      >
        <h2 className="font-black text-foreground">Add a private note</h2>
        <label className="space-y-2 text-sm font-bold text-foreground">
          Note type
          <Select defaultValue="private_note" name="kind">
            <option value="private_note">Private note</option>
            <option value="reflection">Reflection</option>
          </Select>
        </label>
        <SessionTextarea
          id="new-session-note"
          label="Note"
          maxLength={8000}
          name="body"
          required
        />
        <Button disabled={isBusy("note")} type="submit">
          {isBusy("note") ? "Saving…" : "Save private note"}
        </Button>
      </form>
      {notes.length === 0 ? (
        <EmptyState
          description="Capture preparation notes or a reflection after the interview."
          title="No private notes"
        />
      ) : (
        <div className="space-y-3">
          {notes.map((note) => (
            <form
              className="space-y-3 rounded-xl border border-line bg-white p-4 shadow-sm"
              key={`${note.id}-${note.version}`}
              onSubmit={(event) => onSave(note, event)}
            >
              <label className="space-y-2 text-sm font-bold text-foreground">
                Note type
                <Select defaultValue={note.kind} name="kind">
                  <option value="private_note">Private note</option>
                  <option value="reflection">Reflection</option>
                </Select>
              </label>
              <SessionTextarea
                defaultValue={note.body}
                id={`note-${note.id}`}
                label="Private content"
                maxLength={8000}
                name="body"
                required
              />
              <div className="flex flex-wrap gap-2">
                <Button disabled={isBusy(`note-${note.id}`)} type="submit">
                  Save note
                </Button>
                <Button
                  disabled={isBusy(`note-${note.id}`)}
                  onClick={() => onDelete(note)}
                  type="button"
                  variant="danger"
                >
                  Delete note
                </Button>
              </div>
            </form>
          ))}
        </div>
      )}
      {noteCursor && (
        <Button
          disabled={isBusy("more-notes")}
          onClick={onLoadMore}
          variant="secondary"
        >
          Load more notes
        </Button>
      )}
    </div>
  );
}

function DraftsPanel({
  busy,
  draftCursor,
  drafts,
  onLoadMore,
  onSubmit,
  session,
}: {
  busy: boolean;
  draftCursor: string | null;
  drafts: FollowUpDraftSummary[];
  onLoadMore: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  session: InterviewSession;
}) {
  return (
    <div className="space-y-5 pt-5">
      <Alert title="Draft only — no sending capability" tone="warning">
        CareerOS creates grounded text for your review. There is no email,
        calendar, applicant-tracking, or social-network send action in this
        workspace.
      </Alert>
      <form
        className="space-y-4 rounded-xl border border-line bg-white p-4 sm:p-5"
        onSubmit={onSubmit}
      >
        <fieldset className="space-y-3">
          <legend className="font-black text-foreground">
            Claims allowed in this draft
          </legend>
          <p className="text-sm text-muted">
            Select only claims you want the deterministic draft to use.
          </p>
          {session.context.claims.map((claim) => (
            <CheckboxField
              description={`${claim.evidencePins.length} exact eligible evidence pin(s)`}
              id={`draft-claim-${claim.sourceClaimId}`}
              key={claim.sourceClaimId}
              label={claim.text}
              name="draftClaimId"
              value={claim.sourceClaimId}
            />
          ))}
        </fieldset>
        <Button
          disabled={busy || session.groundingStatus !== "current"}
          type="submit"
        >
          <ShieldCheck aria-hidden="true" className="size-4" />
          {busy
            ? "Creating draft…"
            : session.groundingStatus !== "current"
              ? "Review evidence before drafting"
              : "Create grounded review draft"}
        </Button>
      </form>
      {drafts.length === 0 ? (
        <EmptyState
          description="Choose grounded claims above to create a user-reviewed draft. Nothing will be sent."
          title="No follow-up drafts"
        />
      ) : (
        <div className="space-y-4">
          {drafts.map((draft) => (
            <article
              className="rounded-xl border border-line bg-white p-4 shadow-sm sm:p-5"
              key={draft.id}
            >
              <div className="flex flex-wrap gap-2">
                <Badge tone="warning">Review required</Badge>
                <Badge tone="neutral">Not sent</Badge>
                <Badge
                  tone={
                    draft.groundingStatus === "current"
                      ? "success"
                      : draft.groundingStatus === "needs_review"
                        ? "warning"
                        : "neutral"
                  }
                >
                  {draft.groundingStatus === "current"
                    ? "Evidence current"
                    : humanize(draft.groundingStatus)}
                </Badge>
              </div>
              {draft.groundingWarning && (
                <p className="mt-3 text-sm font-semibold text-warning-strong">
                  {draft.groundingWarning}
                </p>
              )}
              <h2 className="mt-3 font-black text-foreground">
                {draft.subject}
              </h2>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-foreground">
                {draft.body}
              </p>
              <p className="mt-4 text-xs text-muted">
                Grounded in {draft.sourceClaimCount} claim(s) · Content SHA-256:{" "}
                <code className="break-all">{draft.contentSha256}</code>
              </p>
            </article>
          ))}
        </div>
      )}
      {draftCursor && (
        <Button onClick={onLoadMore} variant="secondary">
          Load more drafts
        </Button>
      )}
    </div>
  );
}

function SessionInput({
  id,
  label,
  ...props
}: React.ComponentProps<typeof Input> & { id: string; label: string }) {
  return (
    <label className="space-y-2 text-sm font-bold text-foreground" htmlFor={id}>
      {label}
      <Input id={id} {...props} />
    </label>
  );
}

function SessionTextarea({
  id,
  label,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement> & {
  id: string;
  label: string;
}) {
  return (
    <label className="space-y-2 text-sm font-bold text-foreground" htmlFor={id}>
      {label}
      <textarea
        className="min-h-28 w-full rounded-lg border border-line bg-white px-3 py-2 text-sm font-normal text-foreground outline-none transition focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/25"
        id={id}
        {...props}
      />
    </label>
  );
}
