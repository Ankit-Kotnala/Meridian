import type {
  ApplicationDocumentKind,
  ApplicationEventKind,
  ApplicationSort,
  ApplicationStage,
  ApplicationViewMode,
  OutcomeStatus,
  ReferralStatus,
} from "../api/types";

export const applicationStages = [
  "saved",
  "researching",
  "preparing",
  "ready_to_apply",
  "applied",
  "recruiter_screen",
  "interview",
  "assessment",
  "offer",
  "rejected",
  "withdrawn",
] as const satisfies readonly ApplicationStage[];

export const allowedStageTransitions: Readonly<
  Record<ApplicationStage, readonly ApplicationStage[]>
> = {
  applied: [
    "recruiter_screen",
    "interview",
    "assessment",
    "offer",
    "rejected",
    "withdrawn",
  ],
  assessment: ["interview", "offer", "rejected", "withdrawn"],
  interview: [
    "recruiter_screen",
    "assessment",
    "offer",
    "rejected",
    "withdrawn",
  ],
  offer: ["rejected", "withdrawn"],
  preparing: [
    "researching",
    "ready_to_apply",
    "applied",
    "rejected",
    "withdrawn",
  ],
  ready_to_apply: ["preparing", "applied", "rejected", "withdrawn"],
  recruiter_screen: [
    "applied",
    "interview",
    "assessment",
    "offer",
    "rejected",
    "withdrawn",
  ],
  rejected: ["saved", "researching", "preparing", "ready_to_apply", "applied"],
  researching: [
    "saved",
    "preparing",
    "ready_to_apply",
    "applied",
    "rejected",
    "withdrawn",
  ],
  saved: [
    "researching",
    "preparing",
    "ready_to_apply",
    "applied",
    "rejected",
    "withdrawn",
  ],
  withdrawn: ["saved", "researching", "preparing", "ready_to_apply", "applied"],
};

export const applicationViews = [
  { label: "Board", value: "board" },
  { label: "Table", value: "table" },
  { label: "Calendar", value: "calendar" },
] as const satisfies ReadonlyArray<{
  label: string;
  value: ApplicationViewMode;
}>;

export const applicationSorts = [
  { label: "Recently updated", value: "updated_desc" },
  { label: "Deadline first", value: "deadline_asc" },
] as const satisfies ReadonlyArray<{
  label: string;
  value: ApplicationSort;
}>;

export const referralStatuses = [
  "none",
  "needed",
  "requested",
  "referred",
] as const satisfies readonly ReferralStatus[];

export const outcomeStatuses = [
  "none",
  "offer",
  "rejected",
  "withdrawn",
] as const satisfies readonly OutcomeStatus[];

export const eventKinds = [
  "interview",
  "contact",
  "custom",
] as const satisfies readonly ApplicationEventKind[];

export const documentKinds = [
  "tailored_resume",
  "cover_letter",
  "professional_bio",
  "interest_answer",
  "fit_answer",
  "recruiter_message",
  "hiring_manager_message",
  "referral_request",
  "linkedin_connection_note",
  "follow_up_email",
  "interview_introduction",
  "achievement_summary",
] as const satisfies readonly ApplicationDocumentKind[];

export function humanize(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "Not set";
  const date = new Date(`${value.slice(0, 10)}T12:00:00Z`);
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function stageTone(stage: ApplicationStage) {
  if (stage === "offer") return "success" as const;
  if (stage === "rejected" || stage === "withdrawn") return "neutral" as const;
  if (stage === "applied" || stage === "interview") return "primary" as const;
  return "warning" as const;
}

export function consistencyTone(status: "passed" | "warning" | "failed") {
  if (status === "passed") return "success" as const;
  if (status === "failed") return "danger" as const;
  return "warning" as const;
}
