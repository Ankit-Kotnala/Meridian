import type { components } from "@rezumi/contracts";

export type Application = components["schemas"]["ApplicationSummaryResponse"];
export type ApplicationDetail = components["schemas"]["ApplicationResponse"];
export type ApplicationPage = components["schemas"]["ApplicationPageResponse"];
export type ApplicationCalendar =
  components["schemas"]["ApplicationCalendarResponse"];
export type ApplicationCalendarItem =
  components["schemas"]["ApplicationCalendarItemResponse"];
export type ApplicationTask = components["schemas"]["ApplicationTaskResponse"];
export type ApplicationTaskPage =
  components["schemas"]["ApplicationTaskPageResponse"];
export type ApplicationNote = components["schemas"]["ApplicationNoteResponse"];
export type ApplicationNotePage =
  components["schemas"]["ApplicationNotePageResponse"];
export type ApplicationEvent =
  components["schemas"]["ApplicationEventResponse"];
export type ApplicationEventPage =
  components["schemas"]["ApplicationEventPageResponse"];
export type ApplicationPack = components["schemas"]["ApplicationPackResponse"];
export type ApplicationPackSummary =
  components["schemas"]["ApplicationPackSummaryResponse"];
export type ApplicationPackPage =
  components["schemas"]["ApplicationPackPageResponse"];
export type ApplicationDocument =
  components["schemas"]["ApplicationDocumentResponse"];
export type ApplicationConsistency =
  components["schemas"]["ApplicationConsistencyResponse"];

export type ApplicationCreateInput =
  components["schemas"]["ApplicationCreateRequest"];
export type ApplicationUpdateInput =
  components["schemas"]["ApplicationUpdateRequest"];
export type ApplicationStageUpdateInput =
  components["schemas"]["ApplicationStageUpdateRequest"];
export type ApplicationTaskCreateInput =
  components["schemas"]["ApplicationTaskCreateRequest"];
export type ApplicationTaskUpdateInput =
  components["schemas"]["ApplicationTaskUpdateRequest"];
export type ApplicationNoteCreateInput =
  components["schemas"]["ApplicationNoteCreateRequest"];
export type ApplicationEventCreateInput =
  components["schemas"]["ApplicationEventCreateRequest"];
export type ApplicationPackCreateInput =
  components["schemas"]["ApplicationPackCreateRequest"];

export type ApplicationProfile =
  components["schemas"]["ApplicationProfileResponse"];
export type ApplicationProfileInput =
  components["schemas"]["ApplicationProfileUpsertRequest"];
export type ApplicationProfileLink =
  components["schemas"]["ApplicationProfileLinkInput"];

export type SavedJob = components["schemas"]["JobResponse"];
export type SavedJobPage = components["schemas"]["JobPageResponse"];
export type SavedResume = components["schemas"]["ResumeResponse"];
export type SavedResumeVersion = components["schemas"]["ResumeVersionResponse"];

export type ApplicationStage = Application["stage"];
export type ReferralStatus = Application["referralStatus"];
export type OutcomeStatus = Application["outcomeStatus"];
export type ApplicationEventKind = ApplicationEventCreateInput["eventKind"];
export type ApplicationDocumentKind = ApplicationDocument["kind"];
export type ApplicationViewMode = "board" | "table" | "calendar";
export type ApplicationSort = "updated_desc" | "deadline_asc";
