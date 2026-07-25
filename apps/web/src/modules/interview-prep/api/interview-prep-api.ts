"use client";

import {
  ApiRequestError,
  apiMutation,
  apiQuery,
} from "@/shared/api/browser-request";

import { interviewPrepPaths, withInterviewQuery } from "./paths";
import type {
  ApplicationPage,
  DefenseMap,
  FollowUpDraft,
  FollowUpDraftGenerateInput,
  FollowUpDraftPage,
  GeneratedQuestionBank,
  InterviewQuestion,
  InterviewQuestionCreateInput,
  InterviewQuestionPage,
  InterviewSession,
  InterviewSessionCreateInput,
  InterviewSessionPage,
  InterviewSessionUpdateInput,
  PageOptions,
  SessionNote,
  SessionNoteInput,
  SessionNotePage,
  StarStory,
  StarStoryCreateInput,
  StarStoryPage,
  StarStoryUpdateInput,
  StoryStatus,
} from "./types";

function mutationHeaders(
  version?: number,
  idempotencyKey?: string,
): HeadersInit {
  return {
    ...(version === undefined ? {} : { "If-Match": `"${version}"` }),
    ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
  };
}

async function query(
  path: Parameters<typeof apiQuery>[0],
  signal?: AbortSignal,
) {
  return apiQuery(path, {
    retryAfterRefresh: true,
    ...(signal ? { signal } : {}),
  });
}

async function mutate(
  path: Parameters<typeof apiMutation>[0],
  init: Parameters<typeof apiMutation>[1],
) {
  return apiMutation(path, init, { csrf: "session" });
}

export async function listInterviewApplications(
  options: {
    cursor?: string;
    limit?: number;
    q?: string;
    signal?: AbortSignal;
  } = {},
): Promise<ApplicationPage> {
  const response = await query(
    withInterviewQuery(interviewPrepPaths.applications, {
      cursor: options.cursor,
      limit: options.limit ?? 50,
      q: options.q || undefined,
    }),
    options.signal,
  );
  return (await response.json()) as ApplicationPage;
}

export async function listStories(
  options: PageOptions & {
    applicationId?: string;
    status?: StoryStatus | "";
  } = {},
): Promise<StarStoryPage> {
  const response = await query(
    withInterviewQuery(interviewPrepPaths.stories, {
      applicationId: options.applicationId,
      cursor: options.cursor,
      limit: options.limit ?? 50,
      status: options.status || undefined,
    }),
    options.signal,
  );
  return (await response.json()) as StarStoryPage;
}

export async function getStory(
  storyId: string,
  signal?: AbortSignal,
): Promise<StarStory> {
  const response = await query(interviewPrepPaths.story(storyId), signal);
  return (await response.json()) as StarStory;
}

export async function createStory(
  input: StarStoryCreateInput,
  idempotencyKey: string,
): Promise<StarStory> {
  const response = await mutate(interviewPrepPaths.stories, {
    body: JSON.stringify(input),
    headers: mutationHeaders(undefined, idempotencyKey),
    method: "POST",
  });
  return (await response.json()) as StarStory;
}

export async function updateStory(
  story: Pick<StarStory, "id" | "version">,
  input: StarStoryUpdateInput,
): Promise<StarStory> {
  const response = await mutate(interviewPrepPaths.story(story.id), {
    body: JSON.stringify(input),
    headers: mutationHeaders(story.version),
    method: "PATCH",
  });
  return (await response.json()) as StarStory;
}

export async function deleteStory(
  story: Pick<StarStory, "id" | "version">,
): Promise<void> {
  await mutate(interviewPrepPaths.story(story.id), {
    headers: mutationHeaders(story.version),
    method: "DELETE",
  });
}

export async function getDefenseMap(
  applicationId: string,
  signal?: AbortSignal,
): Promise<DefenseMap> {
  const response = await query(
    interviewPrepPaths.defenseMap(applicationId),
    signal,
  );
  return (await response.json()) as DefenseMap;
}

export async function listSessions(
  options: PageOptions & { applicationId?: string } = {},
): Promise<InterviewSessionPage> {
  const response = await query(
    withInterviewQuery(interviewPrepPaths.sessions, {
      applicationId: options.applicationId,
      cursor: options.cursor,
      limit: options.limit ?? 50,
    }),
    options.signal,
  );
  return (await response.json()) as InterviewSessionPage;
}

export async function getSession(
  sessionId: string,
  signal?: AbortSignal,
): Promise<InterviewSession> {
  const response = await query(interviewPrepPaths.session(sessionId), signal);
  return (await response.json()) as InterviewSession;
}

export async function createSession(
  input: InterviewSessionCreateInput,
  idempotencyKey: string,
): Promise<InterviewSession> {
  const response = await mutate(interviewPrepPaths.sessions, {
    body: JSON.stringify(input),
    headers: mutationHeaders(undefined, idempotencyKey),
    method: "POST",
  });
  return (await response.json()) as InterviewSession;
}

export async function updateSession(
  session: Pick<InterviewSession, "id" | "version">,
  input: InterviewSessionUpdateInput,
): Promise<InterviewSession> {
  const response = await mutate(interviewPrepPaths.session(session.id), {
    body: JSON.stringify(input),
    headers: mutationHeaders(session.version),
    method: "PATCH",
  });
  return (await response.json()) as InterviewSession;
}

export async function deleteSession(
  session: Pick<InterviewSession, "id" | "version">,
): Promise<void> {
  await mutate(interviewPrepPaths.session(session.id), {
    headers: mutationHeaders(session.version),
    method: "DELETE",
  });
}

export async function listQuestions(
  sessionId: string,
  options: PageOptions = {},
): Promise<InterviewQuestionPage> {
  const response = await query(
    withInterviewQuery(interviewPrepPaths.questions(sessionId), {
      cursor: options.cursor,
      limit: options.limit ?? 50,
    }),
    options.signal,
  );
  return (await response.json()) as InterviewQuestionPage;
}

export async function createQuestion(
  sessionId: string,
  input: InterviewQuestionCreateInput,
  idempotencyKey: string,
): Promise<InterviewQuestion> {
  const response = await mutate(interviewPrepPaths.questions(sessionId), {
    body: JSON.stringify(input),
    headers: mutationHeaders(undefined, idempotencyKey),
    method: "POST",
  });
  return (await response.json()) as InterviewQuestion;
}

export async function generateQuestionBank(
  sessionId: string,
  idempotencyKey: string,
): Promise<GeneratedQuestionBank> {
  const response = await mutate(
    interviewPrepPaths.questionGenerate(sessionId),
    {
      headers: mutationHeaders(undefined, idempotencyKey),
      method: "POST",
    },
  );
  return (await response.json()) as GeneratedQuestionBank;
}

export async function listSessionNotes(
  sessionId: string,
  options: PageOptions = {},
): Promise<SessionNotePage> {
  const response = await query(
    withInterviewQuery(interviewPrepPaths.notes(sessionId), {
      cursor: options.cursor,
      limit: options.limit ?? 50,
    }),
    options.signal,
  );
  return (await response.json()) as SessionNotePage;
}

export async function createSessionNote(
  sessionId: string,
  input: SessionNoteInput,
  idempotencyKey: string,
): Promise<SessionNote> {
  const response = await mutate(interviewPrepPaths.notes(sessionId), {
    body: JSON.stringify(input),
    headers: mutationHeaders(undefined, idempotencyKey),
    method: "POST",
  });
  return (await response.json()) as SessionNote;
}

export async function updateSessionNote(
  sessionId: string,
  note: Pick<SessionNote, "id" | "version">,
  input: SessionNoteInput,
): Promise<SessionNote> {
  const response = await mutate(interviewPrepPaths.note(sessionId, note.id), {
    body: JSON.stringify(input),
    headers: mutationHeaders(note.version),
    method: "PATCH",
  });
  return (await response.json()) as SessionNote;
}

export async function deleteSessionNote(
  sessionId: string,
  note: Pick<SessionNote, "id" | "version">,
): Promise<void> {
  await mutate(interviewPrepPaths.note(sessionId, note.id), {
    headers: mutationHeaders(note.version),
    method: "DELETE",
  });
}

export async function listFollowUpDrafts(
  sessionId: string,
  options: PageOptions = {},
): Promise<FollowUpDraftPage> {
  const response = await query(
    withInterviewQuery(interviewPrepPaths.followUpDrafts(sessionId), {
      cursor: options.cursor,
      limit: options.limit ?? 50,
    }),
    options.signal,
  );
  return (await response.json()) as FollowUpDraftPage;
}

export async function generateFollowUpDraft(
  sessionId: string,
  input: FollowUpDraftGenerateInput,
  idempotencyKey: string,
): Promise<FollowUpDraft> {
  const response = await mutate(
    interviewPrepPaths.followUpGenerate(sessionId),
    {
      body: JSON.stringify(input),
      headers: mutationHeaders(undefined, idempotencyKey),
      method: "POST",
    },
  );
  return (await response.json()) as FollowUpDraft;
}

export { ApiRequestError };
