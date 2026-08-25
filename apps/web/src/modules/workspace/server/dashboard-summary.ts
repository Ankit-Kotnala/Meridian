import type { GeneratedApiPath } from "@/shared/api/api-path";
import { serverApiFetch } from "@/shared/api/server-request";

import { workspaceSummaryPaths } from "../api/paths";

/**
 * A count the workspace home can display. `atLeast` is set when the underlying
 * cursor page was full, so the UI shows "100+" instead of implying an exact
 * total the API never promised. Unavailable is rendered explicitly rather than
 * being collapsed into a zero.
 */
export type DashboardCount =
  { atLeast: boolean; kind: "count"; value: number } | { kind: "unavailable" };

export type DashboardAttentionItem = {
  description: string;
  href: string;
  id: string;
  label: string;
  tone: "danger" | "info" | "warning";
};

export type DashboardPipelineGroup = {
  count: number;
  key: "applied" | "closed" | "exploring" | "interviewing" | "offer";
  label: string;
};

export type DashboardPipeline =
  | {
      atLeast: boolean;
      groups: readonly DashboardPipelineGroup[];
      kind: "ready";
      openTasks: number;
      total: number;
    }
  | { kind: "unavailable" };

export type DashboardRecordCounts = {
  achievements: DashboardCount;
  evidence: DashboardCount;
  /** Evidence a person has confirmed, which is what Corp ID standing reads. */
  evidenceConfirmed: DashboardCount;
  experiences: DashboardCount;
  skills: DashboardCount;
};

/**
 * Cross-module state the workspace home projects into the activation chain. The
 * chain itself is derived in the view; this only reports what each owning module
 * currently persists.
 */
export type DashboardActivation = {
  jobs: DashboardCount;
  pendingImports: DashboardCount;
};

export type DashboardJobHunt =
  | { atLeast: boolean; kind: "ready"; total: number; topTitle: string | null }
  | { kind: "unavailable" };

export type DashboardGrowth =
  | { inProgress: number; kind: "ready"; planned: number }
  | { kind: "unavailable" };

export type DashboardPrepare =
  | { followUpsDue: number; kind: "ready" }
  | { kind: "unavailable" };

export type DashboardSummary = {
  activation: DashboardActivation;
  attention: readonly DashboardAttentionItem[];
  attentionDegraded: boolean;
  growth: DashboardGrowth;
  jobHunt: DashboardJobHunt;
  pipeline: DashboardPipeline;
  prepare: DashboardPrepare;
  record: DashboardRecordCounts;
};

const UNAVAILABLE = { kind: "unavailable" } as const;

const EMPTY_SUMMARY: DashboardSummary = {
  activation: { jobs: UNAVAILABLE, pendingImports: UNAVAILABLE },
  attention: [],
  attentionDegraded: true,
  growth: UNAVAILABLE,
  jobHunt: UNAVAILABLE,
  pipeline: UNAVAILABLE,
  prepare: UNAVAILABLE,
  record: {
    achievements: UNAVAILABLE,
    evidence: UNAVAILABLE,
    evidenceConfirmed: UNAVAILABLE,
    experiences: UNAVAILABLE,
    skills: UNAVAILABLE,
  },
};

const DEADLINE_HORIZON_DAYS = 14;

function asRecord(value: unknown): Record<string, unknown> | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function asList(value: unknown): readonly unknown[] {
  return Array.isArray(value) ? value : [];
}

function asText(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function asCount(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) && value > 0
    ? Math.floor(value)
    : 0;
}

function hasMore(payload: Record<string, unknown>): boolean {
  return asRecord(payload.page)?.hasMore === true;
}

function counted(value: number, atLeast = false): DashboardCount {
  return { atLeast, kind: "count", value };
}

/** Fetch and JSON-decode one summary endpoint, degrading instead of throwing. */
async function readJson(
  path: GeneratedApiPath,
): Promise<Record<string, unknown> | null> {
  try {
    const response = await serverApiFetch(path);
    if (!response.ok) return null;
    return asRecord(await response.json());
  } catch {
    return null;
  }
}

function isoDay(offsetDays = 0): string {
  const value = new Date();
  value.setUTCDate(value.getUTCDate() + offsetDays);
  return value.toISOString().slice(0, 10);
}

function plural(value: number, singular: string, pluralForm: string): string {
  return value === 1 ? singular : pluralForm;
}

type ExperienceSummary = {
  conflicts: number;
  count: DashboardCount;
};

function readExperiences(
  payload: Record<string, unknown> | null,
): ExperienceSummary {
  if (!payload) return { conflicts: 0, count: UNAVAILABLE };
  return {
    conflicts: asList(payload.findings).length,
    count: counted(asList(payload.data).length),
  };
}

type SkillSummary = {
  count: DashboardCount;
  unconfirmed: number;
};

function readSkills(payload: Record<string, unknown> | null): SkillSummary {
  if (!payload) return { count: UNAVAILABLE, unconfirmed: 0 };
  const skills = asList(payload.data).map(asRecord);
  return {
    count: counted(skills.length),
    unconfirmed: skills.filter((skill) => skill?.userConfirmed !== true).length,
  };
}

type EvidenceSummary = {
  confirmed: DashboardCount;
  count: DashboardCount;
  notCitable: number;
};

function readEvidence(
  payload: Record<string, unknown> | null,
): EvidenceSummary {
  if (!payload) {
    return { confirmed: UNAVAILABLE, count: UNAVAILABLE, notCitable: 0 };
  }
  const records = asList(payload.data).map(asRecord);
  const states = records.map((record) => asText(record?.state));
  const notCitable = states.filter(
    (state) => state === "inferred" || state === "unsupported",
  ).length;
  return {
    confirmed: counted(
      states.filter((state) => state === "confirmed" || state === "verified")
        .length,
      hasMore(payload),
    ),
    count: counted(records.length, hasMore(payload)),
    notCitable,
  };
}

type AchievementSummary = {
  count: DashboardCount;
  drafts: number;
  ready: number;
};

function readAchievements(
  payload: Record<string, unknown> | null,
): AchievementSummary {
  if (!payload) return { count: UNAVAILABLE, drafts: 0, ready: 0 };
  const statuses = asList(payload.data).map((item) =>
    asText(asRecord(item)?.status),
  );
  const open = statuses.filter(
    (status) => status === "draft" || status === "ready",
  );
  return {
    count: counted(open.length, hasMore(payload)),
    drafts: statuses.filter((status) => status === "draft").length,
    ready: statuses.filter((status) => status === "ready").length,
  };
}

const PIPELINE_GROUPS: readonly {
  key: DashboardPipelineGroup["key"];
  label: string;
  stages: readonly string[];
}[] = [
  {
    key: "exploring",
    label: "Exploring",
    stages: ["saved", "researching", "preparing", "ready_to_apply"],
  },
  { key: "applied", label: "Applied", stages: ["applied"] },
  {
    key: "interviewing",
    label: "Interviewing",
    stages: ["recruiter_screen", "interview", "assessment"],
  },
  { key: "offer", label: "Offer", stages: ["offer"] },
  { key: "closed", label: "Closed", stages: ["rejected", "withdrawn"] },
];

type ApplicationSummary = {
  deadlinesSoon: number;
  followUpsDue: number;
  pipeline: DashboardPipeline;
};

function readApplications(
  payload: Record<string, unknown> | null,
): ApplicationSummary {
  if (!payload) {
    return { deadlinesSoon: 0, followUpsDue: 0, pipeline: UNAVAILABLE };
  }
  const applications = asList(payload.data).map(asRecord);
  const today = isoDay();
  const horizon = isoDay(DEADLINE_HORIZON_DAYS);

  const stageCounts = new Map<string, number>();
  let openTasks = 0;
  let deadlinesSoon = 0;
  let followUpsDue = 0;

  for (const application of applications) {
    const stage = asText(application?.stage);
    stageCounts.set(stage, (stageCounts.get(stage) ?? 0) + 1);
    openTasks += asCount(application?.openTaskCount);

    const closed = stage === "rejected" || stage === "withdrawn";
    if (closed) continue;

    const deadline = asText(application?.applicationDeadline);
    if (deadline && deadline >= today && deadline <= horizon) deadlinesSoon++;

    const followUp = asText(application?.followUpAt);
    if (followUp && followUp <= today) followUpsDue++;
  }

  return {
    deadlinesSoon,
    followUpsDue,
    pipeline: {
      atLeast: hasMore(payload),
      groups: PIPELINE_GROUPS.map(({ key, label, stages }) => ({
        count: stages.reduce(
          (total, stage) => total + (stageCounts.get(stage) ?? 0),
          0,
        ),
        key,
        label,
      })),
      kind: "ready",
      openTasks,
      total: applications.length,
    },
  };
}

function readDueReminders(payload: Record<string, unknown> | null): number {
  return payload ? asList(payload.data).length : 0;
}

/** Count proposals still awaiting a person, across both import proposal kinds. */
function readPendingImports(
  semantic: Record<string, unknown> | null,
  typed: Record<string, unknown> | null,
): DashboardCount {
  if (!semantic && !typed) return UNAVAILABLE;
  const pending = [semantic, typed]
    .filter((payload): payload is Record<string, unknown> => payload !== null)
    .flatMap((payload) => asList(payload.data))
    .filter((item) => asText(asRecord(item)?.status) === "pending");
  const atLeast = [semantic, typed].some(
    (payload) => payload !== null && hasMore(payload),
  );
  return counted(pending.length, atLeast);
}

function readJobs(payload: Record<string, unknown> | null): DashboardCount {
  if (!payload) return UNAVAILABLE;
  return counted(asList(payload.data).length, hasMore(payload));
}

/** `job-catalog` has no `data`/`page` envelope — it returns `listings` directly. */
function readJobHunt(payload: Record<string, unknown> | null): DashboardJobHunt {
  if (!payload) return UNAVAILABLE;
  const listings = asList(payload.listings).map(asRecord);
  const top = listings[0];
  return {
    atLeast: listings.length >= 25,
    kind: "ready",
    topTitle: top ? asText(top.title) || null : null,
    total: listings.length,
  };
}

function readGrowth(payload: Record<string, unknown> | null): DashboardGrowth {
  if (!payload) return UNAVAILABLE;
  const statuses = asList(payload.data).map((item) =>
    asText(asRecord(item)?.status),
  );
  return {
    inProgress: statuses.filter((status) => status === "in_progress").length,
    kind: "ready",
    planned: statuses.filter((status) => status === "planned").length,
  };
}

function readPrepare(payload: Record<string, unknown> | null): DashboardPrepare {
  if (!payload) return UNAVAILABLE;
  return { followUpsDue: asList(payload.data).length, kind: "ready" };
}

function attentionItems({
  achievements,
  applications,
  dueReminders,
  evidence,
  experiences,
  pendingImports,
  skills,
}: {
  achievements: AchievementSummary;
  applications: ApplicationSummary;
  dueReminders: number;
  evidence: EvidenceSummary;
  experiences: ExperienceSummary;
  pendingImports: DashboardCount;
  skills: SkillSummary;
}): readonly DashboardAttentionItem[] {
  const items: DashboardAttentionItem[] = [];

  if (pendingImports.kind === "count" && pendingImports.value > 0) {
    const total = pendingImports.value;
    items.push({
      description: `${total} ${plural(total, "detail from your resume is", "details from your resume are")} waiting for you to accept or reject.`,
      href: "/career-profile/imports",
      id: "pending-imports",
      label: "Review imported resume details",
      tone: "warning",
    });
  }
  if (experiences.conflicts > 0) {
    items.push({
      description: `Your profile has ${experiences.conflicts} ${plural(experiences.conflicts, "date conflict", "date conflicts")} between roles. Fixing them keeps your timeline accurate.`,
      href: "/career-profile",
      id: "profile-conflicts",
      label: "Fix overlapping role dates",
      tone: "danger",
    });
  }
  if (applications.pipeline.kind === "ready") {
    if (applications.deadlinesSoon > 0) {
      items.push({
        description: `${applications.deadlinesSoon} open ${plural(applications.deadlinesSoon, "application closes", "applications close")} within ${DEADLINE_HORIZON_DAYS} days.`,
        href: "/applications",
        id: "application-deadlines",
        label: "Deadlines approaching",
        tone: "warning",
      });
    }
    if (applications.followUpsDue > 0) {
      items.push({
        description: `${applications.followUpsDue} ${plural(applications.followUpsDue, "application has", "applications have")} a follow-up date that has already passed.`,
        href: "/applications",
        id: "application-follow-ups",
        label: "Follow-ups are due",
        tone: "warning",
      });
    }
    if (applications.pipeline.openTasks > 0) {
      items.push({
        description: `${applications.pipeline.openTasks} open ${plural(applications.pipeline.openTasks, "task is", "tasks are")} tracked across your applications.`,
        href: "/applications",
        id: "application-tasks",
        label: "Open application tasks",
        tone: "info",
      });
    }
  }
  if (evidence.notCitable > 0) {
    items.push({
      description: `${evidence.notCitable} ${plural(evidence.notCitable, "item needs", "items need")} stronger proof before you can cite ${plural(evidence.notCitable, "it", "them")} in applications.`,
      href: "/evidence",
      id: "evidence-confirmation",
      label: "Strengthen your evidence",
      tone: "warning",
    });
  }
  if (achievements.drafts > 0) {
    items.push({
      description: `${achievements.drafts} captured ${plural(achievements.drafts, "achievement is", "achievements are")} still a draft. Finish the details while they are fresh.`,
      href: "/achievement-inbox",
      id: "achievement-drafts",
      label: "Finish achievement drafts",
      tone: "info",
    });
  }
  if (achievements.ready > 0) {
    items.push({
      description: `${achievements.ready} ${plural(achievements.ready, "achievement is", "achievements are")} ready to add to your profile as structured evidence.`,
      href: "/achievement-inbox",
      id: "achievement-ready",
      label: "Add ready achievements",
      tone: "info",
    });
  }
  if (dueReminders > 0) {
    items.push({
      description: `${dueReminders} networking ${plural(dueReminders, "follow-up is", "follow-ups are")} due today. You send every message yourself.`,
      href: "/networking",
      id: "networking-reminders",
      label: "Networking follow-ups due",
      tone: "info",
    });
  }
  if (skills.unconfirmed > 0) {
    items.push({
      description: `${skills.unconfirmed} ${plural(skills.unconfirmed, "skill was", "skills were")} pulled from your resume and have not been confirmed by you yet.`,
      href: "/career-profile",
      id: "unconfirmed-skills",
      label: "Confirm your skills",
      tone: "info",
    });
  }

  return items;
}

/**
 * Aggregate the signed-in account's own record for the workspace home.
 *
 * Every endpoint is read-only and independently degradable: a failing section
 * renders as explicitly unavailable rather than as an invented zero, and a
 * total failure returns a summary that says nothing it cannot support.
 */
export async function dashboardSummary(): Promise<DashboardSummary> {
  try {
    const [
      achievementPayload,
      applicationPayload,
      developmentItemPayload,
      evidencePayload,
      experiencePayload,
      jobCatalogPayload,
      jobPayload,
      reminderPayload,
      semanticImportPayload,
      skillPayload,
      typedImportPayload,
    ] = await Promise.all([
      readJson(workspaceSummaryPaths.achievements),
      readJson(workspaceSummaryPaths.applications),
      readJson(workspaceSummaryPaths.developmentItems),
      readJson(workspaceSummaryPaths.evidence),
      readJson(workspaceSummaryPaths.experiences),
      readJson(workspaceSummaryPaths.jobCatalog),
      readJson(workspaceSummaryPaths.jobs),
      readJson(workspaceSummaryPaths.dueReminders),
      readJson(workspaceSummaryPaths.semanticImportProposals),
      readJson(workspaceSummaryPaths.skills),
      readJson(workspaceSummaryPaths.importProposals),
    ]);

    const achievements = readAchievements(achievementPayload);
    const applications = readApplications(applicationPayload);
    const evidence = readEvidence(evidencePayload);
    const experiences = readExperiences(experiencePayload);
    const skills = readSkills(skillPayload);
    const dueReminders = readDueReminders(reminderPayload);
    const pendingImports = readPendingImports(
      semanticImportPayload,
      typedImportPayload,
    );

    return {
      activation: { jobs: readJobs(jobPayload), pendingImports },
      attention: attentionItems({
        achievements,
        applications,
        dueReminders,
        evidence,
        experiences,
        pendingImports,
        skills,
      }),
      attentionDegraded: [
        achievementPayload,
        applicationPayload,
        evidencePayload,
        experiencePayload,
        reminderPayload,
        semanticImportPayload,
        skillPayload,
        typedImportPayload,
      ].some((payload) => payload === null),
      growth: readGrowth(developmentItemPayload),
      jobHunt: readJobHunt(jobCatalogPayload),
      pipeline: applications.pipeline,
      prepare: readPrepare(reminderPayload),
      record: {
        achievements: achievements.count,
        evidence: evidence.count,
        evidenceConfirmed: evidence.confirmed,
        experiences: experiences.count,
        skills: skills.count,
      },
    };
  } catch {
    return EMPTY_SUMMARY;
  }
}
