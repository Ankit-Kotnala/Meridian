import type { components } from "@careeros/contracts";

export type ApplicationSummary =
  components["schemas"]["ApplicationSummaryResponse"];
export type ApplicationPage = components["schemas"]["ApplicationPageResponse"];

export type StarStory = components["schemas"]["StarStoryResponse"];
export type StarStorySummary =
  components["schemas"]["StarStorySummaryResponse"];
export type StarStoryPage = components["schemas"]["StarStoryPageResponse"];
export type StarStoryCreateInput =
  components["schemas"]["StarStoryCreateRequest"];
export type StarStoryUpdateInput =
  components["schemas"]["StarStoryUpdateRequest"];
export type StoryClaimSelection =
  components["schemas"]["StoryClaimSelectionInput"];
export type StoryStatus = StarStory["status"];
export type StoryField = StoryClaimSelection["fieldNames"][number];

export type DefenseMap = components["schemas"]["DefenseMapResponse"];
export type DefenseMapEntry = components["schemas"]["DefenseMapEntryResponse"];

export type InterviewSession =
  components["schemas"]["InterviewSessionResponse"];
export type InterviewSessionSummary =
  components["schemas"]["InterviewSessionSummaryResponse"];
export type InterviewSessionPage =
  components["schemas"]["InterviewSessionPageResponse"];
export type InterviewSessionCreateInput =
  components["schemas"]["InterviewSessionCreateRequest"];
export type InterviewSessionUpdateInput =
  components["schemas"]["InterviewSessionUpdateRequest"];
export type InterviewSessionKind = InterviewSession["kind"];

export type InterviewQuestion =
  components["schemas"]["InterviewQuestionResponse"];
export type InterviewQuestionSummary =
  components["schemas"]["InterviewQuestionSummaryResponse"];
export type InterviewQuestionPage =
  components["schemas"]["InterviewQuestionPageResponse"];
export type InterviewQuestionCreateInput =
  components["schemas"]["InterviewQuestionCreateRequest"];
export type GeneratedQuestionBank =
  components["schemas"]["GeneratedQuestionBankResponse"];

export type SessionNote = components["schemas"]["InterviewSessionNoteResponse"];
export type SessionNotePage =
  components["schemas"]["InterviewSessionNotePageResponse"];
export type SessionNoteInput =
  components["schemas"]["InterviewSessionNoteRequest"];

export type FollowUpDraft = components["schemas"]["FollowUpDraftResponse"];
export type FollowUpDraftSummary =
  components["schemas"]["FollowUpDraftSummaryResponse"];
export type FollowUpDraftPage =
  components["schemas"]["FollowUpDraftPageResponse"];
export type FollowUpDraftGenerateInput =
  components["schemas"]["FollowUpDraftGenerateRequest"];

export type PageOptions = {
  cursor?: string;
  limit?: number;
  signal?: AbortSignal;
};
