import type { components } from "@careeros/contracts";

export type Organization = components["schemas"]["OrganizationResponse"];
export type OrganizationPage =
  components["schemas"]["OrganizationPageResponse"];
export type OrganizationCreateInput =
  components["schemas"]["OrganizationCreateRequest"];
export type OrganizationUpdateInput =
  components["schemas"]["OrganizationUpdateRequest"];

export type Contact = components["schemas"]["ContactResponse"];
export type ContactPage = components["schemas"]["ContactPageResponse"];
export type ContactCreateInput = components["schemas"]["ContactCreateRequest"];
export type ContactUpdateInput = components["schemas"]["ContactUpdateRequest"];
export type RelationshipStage = Contact["relationshipStage"];
export type ContactReferralState = Contact["referralState"];

export type ConsentHistory = components["schemas"]["ConsentHistoryResponse"];
export type ConsentEvent = components["schemas"]["ConsentEventResponse"];
export type ConsentChangeInput = components["schemas"]["ConsentChangeRequest"];
export type ConsentPurpose = ConsentChangeInput["purpose"];

export type ContactNote = components["schemas"]["ContactNoteResponse"];
export type ContactNotePage = components["schemas"]["ContactNoteListResponse"];
export type ContactNoteCreateInput =
  components["schemas"]["ContactNoteCreateRequest"];

export type Interaction = components["schemas"]["InteractionResponse"];
export type InteractionPage = components["schemas"]["InteractionListResponse"];
export type InteractionCreateInput =
  components["schemas"]["InteractionCreateRequest"];
export type InteractionKind = Interaction["kind"];
export type InteractionDirection = Interaction["direction"];

export type Referral = components["schemas"]["ReferralResponse"];
export type ReferralPage = components["schemas"]["ReferralListResponse"];
export type ReferralCreateInput =
  components["schemas"]["ReferralCreateRequest"];
export type ReferralUpdateInput =
  components["schemas"]["ReferralUpdateRequest"];
export type ReferralStatus = Referral["status"];

export type NetworkingTemplate = components["schemas"]["TemplateResponse"];
export type NetworkingTemplatePage =
  components["schemas"]["TemplateListResponse"];
export type TemplateCreateInput =
  components["schemas"]["TemplateCreateRequest"];
export type TemplateUpdateInput =
  components["schemas"]["TemplateUpdateRequest"];
export type TemplateKind = NetworkingTemplate["kind"];

export type Reminder = components["schemas"]["ReminderResponse"];
export type ReminderExecution =
  components["schemas"]["ReminderExecutionResponse"];
export type LocalReminderExecution = Omit<
  ReminderExecution,
  "occurrenceStatus"
> & {
  occurrenceStatus: ReminderExecution["occurrenceStatus"] | "due";
};
export type ReminderPage = components["schemas"]["ReminderListResponse"];
export type ReminderCreateInput =
  components["schemas"]["ReminderCreateRequest"];
export type ReminderUpdateInput =
  components["schemas"]["ReminderUpdateRequest"];
export type ReminderStatus = Reminder["status"];

export type ReminderExecutionBatch = {
  data: Array<{
    execution: LocalReminderExecution;
    reminderId: string;
  }>;
};

export type DueReminderPage = {
  data: Array<{
    execution: LocalReminderExecution;
    reminder: Reminder;
  }>;
  page: {
    hasMore: boolean;
    limit: number;
    nextCursor: string | null;
  };
};

export type ReminderResolutionInput =
  | { action: "acknowledge" | "complete"; snoozeUntil?: never }
  | { action: "snooze"; snoozeUntil: string };

export type ApplicationSummary =
  components["schemas"]["ApplicationSummaryResponse"];
export type ApplicationPage = components["schemas"]["ApplicationPageResponse"];

export type PageOptions = {
  cursor?: string;
  limit?: number;
  signal?: AbortSignal;
};
