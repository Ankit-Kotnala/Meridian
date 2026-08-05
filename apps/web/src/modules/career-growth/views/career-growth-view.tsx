"use client";

import {
  Activity,
  BookOpenCheck,
  CalendarCheck,
  Flag,
  History,
  Plus,
  RefreshCcw,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import {
  useCallback,
  useEffect,
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
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Input,
  LoadingSkeleton,
  PageHeader,
  Select,
} from "@careeros/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  analyzeCareerHealth,
  createCareerReview,
  createDevelopmentItem,
  createGoal,
  createMilestone,
  deleteCareerHealth,
  deleteCareerReview,
  deleteDevelopmentItem,
  deleteGoal,
  deleteMilestone,
  finalizeCareerReview,
  getCareerHealth,
  getCareerReview,
  getCareerGrowthInsights,
  getGoal,
  isVersionConflict,
  listCareerHealth,
  listCareerReviews,
  listDevelopmentItems,
  listGoals,
  reviseCareerReview,
  updateDevelopmentItem,
  updateGoal,
  updateMilestone,
} from "../api/career-growth-api";
import type {
  CareerGrowthInsights,
  CareerHealth,
  CareerHealthSummary,
  CareerReview,
  CareerReviewSummary,
  CareerReviewCreateInput,
  CareerReviewReviseInput,
  DevelopmentItem,
  DevelopmentItemCreateInput,
  DevelopmentItemUpdateInput,
  EvidenceLink,
  Goal,
  GoalCreateInput,
  GoalMilestone,
  GoalSummary,
  GoalUpdateInput,
  MilestoneCreateInput,
  MilestoneUpdateInput,
  ReviewContent,
} from "../api/types";

export const CAREER_HEALTH_DISCLAIMER =
  "CareerOS scores are internal readiness measurements. They are not scores provided by an employer or applicant tracking system and do not guarantee interviews or employment outcomes.";

type GrowthData = {
  developmentCursor: string | null;
  developmentItems: DevelopmentItem[];
  goalCursor: string | null;
  goals: Array<Goal | GoalSummary>;
  healthCursor: string | null;
  health: Array<CareerHealth | CareerHealthSummary>;
  insights: CareerGrowthInsights;
  reviewCursor: string | null;
  reviews: Array<CareerReview | CareerReviewSummary>;
};

type GrowthCollection = "development" | "goals" | "health" | "reviews";

type ConfirmAction =
  | { kind: "delete-development"; item: DevelopmentItem }
  | { kind: "delete-goal"; goal: Goal }
  | { kind: "delete-health"; analysis: CareerHealth | CareerHealthSummary }
  | { kind: "delete-milestone"; milestone: GoalMilestone }
  | { kind: "delete-review"; review: CareerReview }
  | { kind: "finalize-review"; review: CareerReview }
  | {
      input: CareerReviewReviseInput;
      kind: "revise-review";
      review: CareerReview;
    };

const fieldClass =
  "min-h-28 w-full rounded-xl border border-line bg-surface px-3.5 py-3 text-sm text-foreground shadow-sm outline-none placeholder:text-muted hover:border-line-strong focus:border-primary focus:ring-3 focus:ring-primary-soft disabled:cursor-not-allowed disabled:bg-surface-subtle";

const goalStatuses = ["active", "paused", "completed", "cancelled"] as const;
const milestoneStatuses = [
  "pending",
  "in_progress",
  "completed",
  "cancelled",
] as const;
const developmentKinds = [
  "learning",
  "certification",
  "performance_review",
  "promotion",
  "internal_mobility",
  "annual_resume_refresh",
] as const;
const developmentStatuses = [
  "planned",
  "in_progress",
  "paused",
  "completed",
  "cancelled",
] as const;

function humanize(value: string): string {
  return value
    .replaceAll(/([a-z0-9])([A-Z])/g, "$1 $2")
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formattedDate(value: string | null): string {
  if (!value) return "Not set";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(new Date(`${value.slice(0, 10)}T12:00:00Z`));
}

function formattedDateTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function basisPoints(value: number | null): string {
  return value === null ? "Not applicable" : `${(value / 100).toFixed(1)}%`;
}

function parseEvidenceIds(value: FormDataEntryValue | null): string[] {
  return String(value ?? "")
    .split(/[\s,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function evidenceValue(links: EvidenceLink[]): string {
  return links.map((link) => link.evidenceId).join("\n");
}

function optionalText(value: FormDataEntryValue | null): string | null {
  const text = String(value ?? "").trim();
  return text || null;
}

function intentKey(prefix: string): string {
  const id =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `career-growth.${prefix}.${id}`;
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function toneForStatus(
  status: string,
): "danger" | "neutral" | "primary" | "success" | "warning" {
  if (status === "completed" || status === "finalized") return "success";
  if (status === "active" || status === "in_progress") return "primary";
  if (status === "cancelled") return "danger";
  if (status === "paused" || status === "needs_attention") return "warning";
  return "neutral";
}

function appendUnique<T extends { id: string }>(
  current: T[],
  incoming: T[],
): T[] {
  const identifiers = new Set(current.map((item) => item.id));
  return [
    ...current,
    ...incoming.filter((item) => {
      if (identifiers.has(item.id)) return false;
      identifiers.add(item.id);
      return true;
    }),
  ];
}

function prependUnique<T extends { id: string }>(
  current: T[],
  incoming: T,
): T[] {
  return [incoming, ...current.filter((item) => item.id !== incoming.id)];
}

function isGoalDetail(value: Goal | GoalSummary): value is Goal {
  return "milestones" in value;
}

function isReviewDetail(
  value: CareerReview | CareerReviewSummary,
): value is CareerReview {
  return "currentVersion" in value;
}

function isHealthDetail(
  value: CareerHealth | CareerHealthSummary,
): value is CareerHealth {
  return "components" in value;
}

function canonicalPayload(value: unknown, key?: string): unknown {
  if (Array.isArray(value)) {
    const normalized = value.map((item) => canonicalPayload(item));
    return key === "evidenceIds"
      ? [...normalized].sort((left: unknown, right: unknown) =>
          String(left).localeCompare(String(right)),
        )
      : normalized;
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([entryKey, entryValue]) => [
          entryKey,
          canonicalPayload(entryValue, entryKey),
        ]),
    );
  }
  return value;
}

function payloadSignature(value: unknown): string {
  return JSON.stringify(canonicalPayload(value));
}

function Field({ children, label }: { children: ReactNode; label: string }) {
  return (
    <label className="grid gap-1.5 text-sm font-bold text-foreground">
      <span>{label}</span>
      {children}
    </label>
  );
}

function EvidenceLinks({ links }: { links: EvidenceLink[] }) {
  if (links.length === 0) {
    return <p className="text-xs text-muted">No evidence linked.</p>;
  }
  return (
    <ul className="grid gap-2" aria-label="Linked evidence revisions">
      {links.map((link) => (
        <li
          className={`rounded-xl border px-3 py-2 text-xs ${
            link.supportStatus === "current"
              ? "border-line bg-surface-subtle"
              : "border-amber-300 bg-amber-50"
          }`}
          key={link.id}
        >
          <Link
            className="font-bold text-primary underline-offset-4 hover:underline"
            href={`/evidence/${link.evidenceId}`}
          >
            Evidence revision {link.revisionNumber}
          </Link>
          <span className="ml-2 text-muted">
            captured {formattedDateTime(link.evidenceRevisedAt)}
          </span>
          {link.supportStatus === "needs_review" && (
            <p className="mt-1 font-bold text-amber-900">
              Needs review: this pinned revision is no longer current eligible
              evidence.
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}

function EvidenceField({
  defaultLinks = [],
  id,
}: {
  defaultLinks?: EvidenceLink[];
  id: string;
}) {
  return (
    <label
      className="grid gap-1.5 text-sm font-bold text-foreground"
      htmlFor={id}
    >
      Evidence IDs
      <textarea
        className={fieldClass}
        defaultValue={evidenceValue(defaultLinks)}
        id={id}
        name="evidenceIds"
        placeholder="One evidence UUID per line"
      />
      <span className="text-xs font-normal leading-5 text-muted">
        Links are pinned to the current evidence revision so later edits do not
        silently change this record.{" "}
        <Link
          className="font-bold text-primary underline-offset-4 hover:underline"
          href="/evidence"
        >
          Browse the Evidence Vault
        </Link>
        .
      </span>
    </label>
  );
}

function GoalCreateForm({
  busy,
  onCreate,
}: {
  busy: boolean;
  onCreate: (input: GoalCreateInput) => Promise<boolean>;
}) {
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const form = new FormData(target);
    const created = await onCreate({
      description: optionalText(form.get("description")),
      evidenceIds: parseEvidenceIds(form.get("evidenceIds")),
      status: String(form.get("status")) as GoalCreateInput["status"],
      targetDate: optionalText(form.get("targetDate")),
      title: String(form.get("title") ?? "").trim(),
    });
    if (created) target.reset();
  }

  return (
    <details className="rounded-2xl border border-dashed border-primary/35 bg-primary-soft/20 p-4">
      <summary className="cursor-pointer font-extrabold text-primary">
        Add a career goal
      </summary>
      <form
        className="mt-4 grid gap-4"
        onSubmit={(event) => void submit(event)}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Goal title">
            <Input maxLength={240} name="title" required />
          </Field>
          <Field label="Target date">
            <Input name="targetDate" type="date" />
          </Field>
          <Field label="Status">
            <Select defaultValue="active" name="status">
              {goalStatuses.map((status) => (
                <option key={status} value={status}>
                  {humanize(status)}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <Field label="Description">
          <textarea
            className={fieldClass}
            maxLength={4000}
            name="description"
          />
        </Field>
        <EvidenceField id="new-goal-evidence" />
        <Button loading={busy} loadingLabel="Adding goal…" type="submit">
          <Plus aria-hidden="true" className="size-4" />
          Add goal
        </Button>
      </form>
    </details>
  );
}

function GoalSummaryCard({
  busy,
  goal,
  onLoad,
}: {
  busy: boolean;
  goal: GoalSummary;
  onLoad: (goalId: string) => Promise<void>;
}) {
  return (
    <article className="rounded-2xl border border-line bg-surface p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-black">{goal.title}</h3>
            <Badge tone={toneForStatus(goal.status)}>
              {humanize(goal.status)}
            </Badge>
          </div>
          <p className="mt-1 text-sm text-muted">
            Target: {formattedDate(goal.targetDate)} · {goal.milestoneCount}{" "}
            milestone(s) · {goal.evidenceLinkCount} evidence link(s)
          </p>
          {goal.evidenceNeedsReviewCount > 0 && (
            <p className="mt-2 text-sm font-bold text-amber-900">
              {goal.evidenceNeedsReviewCount} linked evidence revision(s) need
              review.
            </p>
          )}
        </div>
        <Button
          loading={busy}
          loadingLabel="Loading goal…"
          onClick={() => void onLoad(goal.id)}
          variant="secondary"
        >
          Load goal details
        </Button>
      </div>
    </article>
  );
}

function GoalCard({
  busyKeys,
  goal,
  onDelete,
  onDeleteMilestone,
  onMilestoneCreate,
  onMilestoneUpdate,
  onUpdate,
}: {
  busyKeys: ReadonlySet<string>;
  goal: Goal;
  onDelete: (goal: Goal) => void;
  onDeleteMilestone: (milestone: GoalMilestone) => void;
  onMilestoneCreate: (
    goal: Goal,
    input: MilestoneCreateInput,
  ) => Promise<boolean>;
  onMilestoneUpdate: (
    milestone: GoalMilestone,
    input: MilestoneUpdateInput,
  ) => Promise<void>;
  onUpdate: (goal: Goal, input: GoalUpdateInput) => Promise<void>;
}) {
  async function saveGoal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await onUpdate(goal, {
      description: optionalText(form.get("description")),
      evidenceIds: parseEvidenceIds(form.get("evidenceIds")),
      status: String(form.get("status")) as GoalUpdateInput["status"],
      targetDate: optionalText(form.get("targetDate")),
      title: String(form.get("title") ?? "").trim(),
    });
  }

  async function addMilestone(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const form = new FormData(target);
    const created = await onMilestoneCreate(goal, {
      evidenceIds: parseEvidenceIds(form.get("evidenceIds")),
      status: String(form.get("status")) as MilestoneCreateInput["status"],
      targetDate: optionalText(form.get("targetDate")),
      title: String(form.get("title") ?? "").trim(),
    });
    if (created) target.reset();
  }

  return (
    <article className="rounded-2xl border border-line bg-surface p-4 shadow-sm sm:p-5">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-black">{goal.title}</h3>
            <Badge tone={toneForStatus(goal.status)}>
              {humanize(goal.status)}
            </Badge>
          </div>
          <p className="mt-1 text-sm text-muted">
            Target: {formattedDate(goal.targetDate)} · Updated{" "}
            {formattedDateTime(goal.updatedAt)}
          </p>
          {goal.description && (
            <p className="mt-3 max-w-3xl text-sm leading-6">
              {goal.description}
            </p>
          )}
        </div>
        <Button
          aria-label={`Delete ${goal.title}`}
          onClick={() => onDelete(goal)}
          variant="ghost"
        >
          <Trash2 aria-hidden="true" className="size-4" />
          Delete
        </Button>
      </header>

      <div className="mt-4">
        <EvidenceLinks links={goal.evidenceLinks} />
      </div>

      <details className="mt-5 rounded-xl border border-line p-4">
        <summary className="cursor-pointer text-sm font-extrabold">
          Edit goal
        </summary>
        <form
          className="mt-4 grid gap-4"
          key={goal.version}
          onSubmit={(event) => void saveGoal(event)}
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Title">
              <Input
                defaultValue={goal.title}
                maxLength={240}
                name="title"
                required
              />
            </Field>
            <Field label="Target date">
              <Input
                defaultValue={goal.targetDate ?? ""}
                name="targetDate"
                type="date"
              />
            </Field>
            <Field label="Status">
              <Select defaultValue={goal.status} name="status">
                {goalStatuses.map((status) => (
                  <option key={status} value={status}>
                    {humanize(status)}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <Field label="Description">
            <textarea
              className={fieldClass}
              defaultValue={goal.description ?? ""}
              maxLength={4000}
              name="description"
            />
          </Field>
          <EvidenceField
            defaultLinks={goal.evidenceLinks}
            id={`goal-${goal.id}-evidence`}
          />
          <Button
            loading={busyKeys.has(`goal-${goal.id}`)}
            loadingLabel="Saving goal…"
            type="submit"
          >
            Save goal
          </Button>
        </form>
      </details>

      <section className="mt-6" aria-labelledby={`milestones-${goal.id}`}>
        <div className="flex items-center justify-between gap-3">
          <h4 className="font-black" id={`milestones-${goal.id}`}>
            Milestones
          </h4>
          <span className="text-xs text-muted">
            {goal.milestones.length} total
          </span>
        </div>
        {goal.milestones.length === 0 ? (
          <p className="mt-3 rounded-xl bg-surface-subtle p-4 text-sm text-muted">
            No milestones yet. Add a concrete next step below.
          </p>
        ) : (
          <ul className="mt-3 grid gap-3">
            {goal.milestones.map((milestone) => (
              <li
                className="rounded-xl border border-line bg-surface-subtle p-4"
                key={milestone.id}
              >
                <form
                  className="grid gap-3"
                  key={milestone.version}
                  onSubmit={(event) => {
                    event.preventDefault();
                    const form = new FormData(event.currentTarget);
                    void onMilestoneUpdate(milestone, {
                      evidenceIds: parseEvidenceIds(form.get("evidenceIds")),
                      status: String(
                        form.get("status"),
                      ) as MilestoneUpdateInput["status"],
                      targetDate: optionalText(form.get("targetDate")),
                      title: String(form.get("title") ?? "").trim(),
                    });
                  }}
                >
                  <div className="grid gap-3 md:grid-cols-[minmax(0,2fr)_minmax(10rem,1fr)_minmax(9rem,1fr)_auto] md:items-end">
                    <Field label="Milestone title">
                      <Input
                        defaultValue={milestone.title}
                        maxLength={240}
                        name="title"
                        required
                      />
                    </Field>
                    <Field label="Status">
                      <Select defaultValue={milestone.status} name="status">
                        {milestoneStatuses.map((status) => (
                          <option key={status} value={status}>
                            {humanize(status)}
                          </option>
                        ))}
                      </Select>
                    </Field>
                    <Field label="Target date">
                      <Input
                        defaultValue={milestone.targetDate ?? ""}
                        name="targetDate"
                        type="date"
                      />
                    </Field>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        loading={busyKeys.has(`milestone-${milestone.id}`)}
                        loadingLabel="Saving…"
                        type="submit"
                        variant="secondary"
                      >
                        Save
                      </Button>
                      <Button
                        aria-label={`Delete milestone ${milestone.title}`}
                        onClick={() => onDeleteMilestone(milestone)}
                        variant="ghost"
                      >
                        <Trash2 aria-hidden="true" className="size-4" />
                      </Button>
                    </div>
                  </div>
                  <EvidenceField
                    defaultLinks={milestone.evidenceLinks}
                    id={`milestone-${milestone.id}-evidence`}
                  />
                  <EvidenceLinks links={milestone.evidenceLinks} />
                </form>
              </li>
            ))}
          </ul>
        )}
        <details className="mt-3 rounded-xl border border-dashed border-line p-4">
          <summary className="cursor-pointer text-sm font-extrabold">
            Add milestone
          </summary>
          <form
            className="mt-4 grid gap-4"
            onSubmit={(event) => void addMilestone(event)}
          >
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Title">
                <Input maxLength={240} name="title" required />
              </Field>
              <Field label="Status">
                <Select defaultValue="pending" name="status">
                  {milestoneStatuses.map((status) => (
                    <option key={status} value={status}>
                      {humanize(status)}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Target date">
                <Input name="targetDate" type="date" />
              </Field>
            </div>
            <EvidenceField id={`new-milestone-${goal.id}-evidence`} />
            <Button
              loading={busyKeys.has(`milestone-new-${goal.id}`)}
              loadingLabel="Adding milestone…"
              type="submit"
            >
              Add milestone
            </Button>
          </form>
        </details>
      </section>
    </article>
  );
}

function DevelopmentCreateForm({
  busy,
  onCreate,
}: {
  busy: boolean;
  onCreate: (input: DevelopmentItemCreateInput) => Promise<boolean>;
}) {
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const form = new FormData(target);
    const created = await onCreate({
      description: optionalText(form.get("description")),
      evidenceIds: parseEvidenceIds(form.get("evidenceIds")),
      kind: String(form.get("kind")) as DevelopmentItemCreateInput["kind"],
      status: String(
        form.get("status"),
      ) as DevelopmentItemCreateInput["status"],
      targetDate: optionalText(form.get("targetDate")),
      title: String(form.get("title") ?? "").trim(),
    });
    if (created) target.reset();
  }

  return (
    <details className="rounded-2xl border border-dashed border-primary/35 bg-primary-soft/20 p-4">
      <summary className="cursor-pointer font-extrabold text-primary">
        Add a development plan item
      </summary>
      <form
        className="mt-4 grid gap-4"
        onSubmit={(event) => void submit(event)}
      >
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Title">
            <Input maxLength={240} name="title" required />
          </Field>
          <Field label="Kind">
            <Select defaultValue="learning" name="kind">
              {developmentKinds.map((kind) => (
                <option key={kind} value={kind}>
                  {humanize(kind)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Status">
            <Select defaultValue="planned" name="status">
              {developmentStatuses.map((status) => (
                <option key={status} value={status}>
                  {humanize(status)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Target date">
            <Input name="targetDate" type="date" />
          </Field>
        </div>
        <Field label="Description">
          <textarea
            className={fieldClass}
            maxLength={4000}
            name="description"
          />
        </Field>
        <EvidenceField id="new-development-evidence" />
        <Button loading={busy} loadingLabel="Adding plan item…" type="submit">
          Add plan item
        </Button>
      </form>
    </details>
  );
}

function DevelopmentCard({
  busy,
  item,
  onDelete,
  onUpdate,
}: {
  busy: boolean;
  item: DevelopmentItem;
  onDelete: (item: DevelopmentItem) => void;
  onUpdate: (
    item: DevelopmentItem,
    input: DevelopmentItemUpdateInput,
  ) => Promise<void>;
}) {
  return (
    <article className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-black">{item.title}</h3>
            <Badge tone={toneForStatus(item.status)}>
              {humanize(item.status)}
            </Badge>
            <Badge>{humanize(item.kind)}</Badge>
          </div>
          <p className="mt-1 text-xs text-muted">
            Target: {formattedDate(item.targetDate)}
          </p>
        </div>
        <Button
          aria-label={`Delete ${item.title}`}
          onClick={() => onDelete(item)}
          variant="ghost"
        >
          <Trash2 aria-hidden="true" className="size-4" />
        </Button>
      </div>
      {item.description && (
        <p className="mt-3 text-sm leading-6">{item.description}</p>
      )}
      <div className="mt-3">
        <EvidenceLinks links={item.evidenceLinks} />
      </div>
      <details className="mt-4 rounded-xl border border-line p-3">
        <summary className="cursor-pointer text-sm font-extrabold">
          Update plan item
        </summary>
        <form
          className="mt-4 grid gap-4"
          key={item.version}
          onSubmit={(event) => {
            event.preventDefault();
            const form = new FormData(event.currentTarget);
            void onUpdate(item, {
              description: optionalText(form.get("description")),
              evidenceIds: parseEvidenceIds(form.get("evidenceIds")),
              kind: String(
                form.get("kind"),
              ) as DevelopmentItemUpdateInput["kind"],
              status: String(
                form.get("status"),
              ) as DevelopmentItemUpdateInput["status"],
              targetDate: optionalText(form.get("targetDate")),
              title: String(form.get("title") ?? "").trim(),
            });
          }}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Title">
              <Input defaultValue={item.title} name="title" required />
            </Field>
            <Field label="Kind">
              <Select defaultValue={item.kind} name="kind">
                {developmentKinds.map((kind) => (
                  <option key={kind} value={kind}>
                    {humanize(kind)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Status">
              <Select defaultValue={item.status} name="status">
                {developmentStatuses.map((status) => (
                  <option key={status} value={status}>
                    {humanize(status)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Target date">
              <Input
                defaultValue={item.targetDate ?? ""}
                name="targetDate"
                type="date"
              />
            </Field>
          </div>
          <Field label="Description">
            <textarea
              className={fieldClass}
              defaultValue={item.description ?? ""}
              maxLength={4000}
              name="description"
            />
          </Field>
          <EvidenceField
            defaultLinks={item.evidenceLinks}
            id={`development-${item.id}-evidence`}
          />
          <Button loading={busy} loadingLabel="Saving plan item…" type="submit">
            Save plan item
          </Button>
        </form>
      </details>
    </article>
  );
}

function ReviewContentFields({
  idPrefix,
  value,
}: {
  idPrefix: string;
  value?: ReviewContent;
}) {
  return (
    <div className="grid gap-4">
      <Field label="Review title">
        <Input
          defaultValue={value?.title ?? ""}
          id={`${idPrefix}-title`}
          maxLength={240}
          name="title"
          required
        />
      </Field>
      <Field label="Summary">
        <textarea
          className={fieldClass}
          defaultValue={value?.summary ?? ""}
          id={`${idPrefix}-summary`}
          maxLength={8000}
          name="summary"
          required
        />
      </Field>
      <div className="grid gap-4 lg:grid-cols-3">
        <Field label="Achievements">
          <textarea
            className={fieldClass}
            defaultValue={value?.achievements ?? ""}
            maxLength={8000}
            name="achievements"
          />
        </Field>
        <Field label="Growth areas">
          <textarea
            className={fieldClass}
            defaultValue={value?.growthAreas ?? ""}
            maxLength={8000}
            name="growthAreas"
          />
        </Field>
        <Field label="Next focus">
          <textarea
            className={fieldClass}
            defaultValue={value?.nextFocus ?? ""}
            maxLength={8000}
            name="nextFocus"
          />
        </Field>
      </div>
    </div>
  );
}

function reviewContent(form: FormData): ReviewContent {
  return {
    achievements: optionalText(form.get("achievements")),
    growthAreas: optionalText(form.get("growthAreas")),
    nextFocus: optionalText(form.get("nextFocus")),
    summary: String(form.get("summary") ?? "").trim(),
    title: String(form.get("title") ?? "").trim(),
  };
}

function ReviewCreateForm({
  busy,
  onCreate,
}: {
  busy: boolean;
  onCreate: (input: CareerReviewCreateInput) => Promise<boolean>;
}) {
  return (
    <details className="rounded-2xl border border-dashed border-primary/35 bg-primary-soft/20 p-4">
      <summary className="cursor-pointer font-extrabold text-primary">
        Start a career review
      </summary>
      <form
        className="mt-4 grid gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          const target = event.currentTarget;
          const form = new FormData(target);
          void onCreate({
            cadence: String(
              form.get("cadence"),
            ) as CareerReviewCreateInput["cadence"],
            content: reviewContent(form),
            evidenceIds: parseEvidenceIds(form.get("evidenceIds")),
            periodEnd: String(form.get("periodEnd") ?? ""),
            periodStart: String(form.get("periodStart") ?? ""),
          }).then((created) => {
            if (created) target.reset();
          });
        }}
      >
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Cadence">
            <Select defaultValue="quarterly" name="cadence">
              <option value="quarterly">Quarterly</option>
              <option value="annual">Annual</option>
            </Select>
          </Field>
          <Field label="Period start">
            <Input name="periodStart" required type="date" />
          </Field>
          <Field label="Period end">
            <Input name="periodEnd" required type="date" />
          </Field>
        </div>
        <ReviewContentFields idPrefix="new-review" />
        <EvidenceField id="new-review-evidence" />
        <Button loading={busy} loadingLabel="Starting review…" type="submit">
          Start draft review
        </Button>
      </form>
    </details>
  );
}

function ReviewSummaryCard({
  busy,
  onLoad,
  review,
}: {
  busy: boolean;
  onLoad: (reviewId: string) => Promise<void>;
  review: CareerReviewSummary;
}) {
  return (
    <article className="rounded-2xl border border-line bg-surface p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-black">{review.currentTitle}</h3>
            <Badge tone={toneForStatus(review.latestStatus)}>
              {humanize(review.latestStatus)}
            </Badge>
          </div>
          <p className="mt-1 text-sm text-muted">
            {humanize(review.cadence)} · {formattedDate(review.periodStart)} to{" "}
            {formattedDate(review.periodEnd)} · {review.historyCount} immutable
            version(s)
          </p>
          {review.evidenceNeedsReviewCount > 0 && (
            <p className="mt-2 text-sm font-bold text-amber-900">
              {review.evidenceNeedsReviewCount} current-version evidence link(s)
              need review.
            </p>
          )}
        </div>
        <Button
          loading={busy}
          loadingLabel="Loading review…"
          onClick={() => void onLoad(review.id)}
          variant="secondary"
        >
          Load review details
        </Button>
      </div>
    </article>
  );
}

function ReviewCard({
  busyKeys,
  onDelete,
  onFinalize,
  onRevise,
  review,
}: {
  busyKeys: ReadonlySet<string>;
  onDelete: (review: CareerReview) => void;
  onFinalize: (review: CareerReview) => void;
  onRevise: (review: CareerReview, input: CareerReviewReviseInput) => void;
  review: CareerReview;
}) {
  const current = review.currentVersion;
  return (
    <article className="rounded-2xl border border-line bg-surface p-4 shadow-sm sm:p-5">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-black">{current.title}</h3>
            <Badge tone={toneForStatus(review.latestStatus)}>
              {humanize(review.latestStatus)}
            </Badge>
            <Badge>Version {review.latestVersionNumber}</Badge>
          </div>
          <p className="mt-1 text-sm text-muted">
            {humanize(review.cadence)} · {formattedDate(review.periodStart)} to{" "}
            {formattedDate(review.periodEnd)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {review.latestStatus === "draft" && (
            <Button onClick={() => onFinalize(review)} variant="secondary">
              <ShieldCheck aria-hidden="true" className="size-4" />
              Finalize
            </Button>
          )}
          <Button onClick={() => onDelete(review)} variant="ghost">
            <Trash2 aria-hidden="true" className="size-4" />
            Delete
          </Button>
        </div>
      </header>

      <div className="mt-4 rounded-xl bg-surface-subtle p-4">
        <p className="text-sm leading-6">{current.summary}</p>
        <dl className="mt-4 grid gap-4 text-sm lg:grid-cols-3">
          <div>
            <dt className="font-extrabold">Achievements</dt>
            <dd className="mt-1 whitespace-pre-wrap text-muted">
              {current.achievements || "Not recorded"}
            </dd>
          </div>
          <div>
            <dt className="font-extrabold">Growth areas</dt>
            <dd className="mt-1 whitespace-pre-wrap text-muted">
              {current.growthAreas || "Not recorded"}
            </dd>
          </div>
          <div>
            <dt className="font-extrabold">Next focus</dt>
            <dd className="mt-1 whitespace-pre-wrap text-muted">
              {current.nextFocus || "Not recorded"}
            </dd>
          </div>
        </dl>
        <div className="mt-4">
          <EvidenceLinks links={current.evidenceLinks} />
        </div>
      </div>

      <details className="mt-4 rounded-xl border border-line p-4">
        <summary className="cursor-pointer text-sm font-extrabold">
          Create a new revision
        </summary>
        <p className="mt-2 text-xs leading-5 text-muted">
          Revisions never overwrite a prior version. Confirming creates a new,
          linked history entry.
        </p>
        <form
          className="mt-4 grid gap-4"
          key={review.latestVersionId}
          onSubmit={(event) => {
            event.preventDefault();
            const form = new FormData(event.currentTarget);
            onRevise(review, {
              changeReason: String(form.get("changeReason") ?? "").trim(),
              content: reviewContent(form),
              evidenceIds: parseEvidenceIds(form.get("evidenceIds")),
            });
          }}
        >
          <ReviewContentFields
            idPrefix={`review-${review.id}`}
            value={{
              achievements: current.achievements,
              growthAreas: current.growthAreas,
              nextFocus: current.nextFocus,
              summary: current.summary,
              title: current.title,
            }}
          />
          <Field label="Reason for this revision">
            <Input maxLength={500} name="changeReason" required />
          </Field>
          <EvidenceField
            defaultLinks={current.evidenceLinks}
            id={`review-${review.id}-evidence`}
          />
          <Button
            loading={busyKeys.has(`review-revise-${review.id}`)}
            loadingLabel="Creating revision…"
            type="submit"
          >
            Review revision
          </Button>
        </form>
      </details>

      <details className="mt-4 rounded-xl border border-line p-4">
        <summary className="cursor-pointer text-sm font-extrabold">
          Immutable history ({review.history.length})
        </summary>
        <ol className="mt-4 grid gap-3">
          {[...review.history]
            .sort((left, right) => right.versionNumber - left.versionNumber)
            .map((version) => (
              <li
                className="rounded-xl border border-line bg-surface-subtle p-3 text-sm"
                key={version.id}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <strong>Version {version.versionNumber}</strong>
                  <Badge tone={toneForStatus(version.status)}>
                    {humanize(version.status)}
                  </Badge>
                  {version.materialChange && (
                    <Badge tone="warning">Material change</Badge>
                  )}
                </div>
                <p className="mt-2 font-bold">{version.title}</p>
                <p className="mt-1 text-muted">{version.changeReason}</p>
                <p className="mt-2 text-xs text-muted">
                  Created {formattedDateTime(version.createdAt)}
                </p>
              </li>
            ))}
        </ol>
      </details>
    </article>
  );
}

function FormulaSnapshot({ snapshot }: { snapshot: Record<string, unknown> }) {
  const entries = Object.entries(snapshot);
  if (entries.length === 0) {
    return <p className="text-sm text-muted">No formula metadata recorded.</p>;
  }
  return (
    <dl className="grid gap-3 sm:grid-cols-2">
      {entries.map(([key, value]) => (
        <div className="rounded-xl bg-surface-subtle p-3" key={key}>
          <dt className="text-xs font-extrabold uppercase tracking-wide text-muted">
            {humanize(key)}
          </dt>
          <dd className="mt-1 break-words text-sm">
            {typeof value === "string" || typeof value === "number"
              ? String(value)
              : JSON.stringify(value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function CareerHealthPanel({
  analyses,
  busyKeys,
  onAnalyze,
  onDelete,
  onLoad,
}: {
  analyses: Array<CareerHealth | CareerHealthSummary>;
  busyKeys: ReadonlySet<string>;
  onAnalyze: () => Promise<void>;
  onDelete: (analysis: CareerHealth | CareerHealthSummary) => void;
  onLoad: (analysisId: string) => Promise<void>;
}) {
  const orderedAnalyses = [...analyses].sort((left, right) =>
    right.createdAt.localeCompare(left.createdAt),
  );
  const latest = orderedAnalyses[0];
  const latestDetail = latest && isHealthDetail(latest) ? latest : undefined;
  return (
    <Card className="p-5 sm:p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-primary">
            Career Health
          </p>
          <h2 className="mt-1 text-2xl font-black tracking-tight">
            A transparent maintenance signal
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            The calculation uses your current goals, evidence currency,
            development follow-through, review cadence, and readiness
            maintenance. Every component remains inspectable.
          </p>
        </div>
        <Button
          loading={busyKeys.has("health-analyze")}
          loadingLabel="Calculating…"
          onClick={() => void onAnalyze()}
        >
          <Activity aria-hidden="true" className="size-4" />
          {latest ? "Recalculate" : "Calculate Career Health"}
        </Button>
      </div>

      {!latest ? (
        <EmptyState
          className="mt-6"
          description="Calculate a snapshot after adding goals, evidence, development items, or reviews."
          title="No Career Health snapshot yet"
        />
      ) : (
        <div className="mt-6 space-y-5">
          <section
            aria-labelledby="career-health-score"
            className="rounded-2xl border border-line bg-surface-subtle p-5"
          >
            {latest.status === "complete" && latest.displayScore !== null ? (
              <>
                <p className="text-sm font-bold text-muted">Career Health</p>
                <div className="mt-1 flex flex-wrap items-end gap-3">
                  <h3
                    className="text-5xl font-black tracking-tight"
                    id="career-health-score"
                  >
                    {latest.displayScore}
                    <span className="text-xl text-muted">/100</span>
                  </h3>
                  <Badge
                    tone={
                      latest.label === "well_maintained"
                        ? "success"
                        : latest.label === "needs_attention"
                          ? "warning"
                          : "primary"
                    }
                  >
                    {humanize(latest.label)}
                  </Badge>
                </div>
              </>
            ) : (
              <>
                <h3 className="text-xl font-black" id="career-health-score">
                  Insufficient data
                </h3>
                <p className="mt-2 text-sm text-muted">
                  {latest.insufficientReason ??
                    "Add more maintained career records before calculating a score."}
                </p>
              </>
            )}
            <p
              className="mt-3 max-w-3xl text-xs font-semibold leading-5 text-muted"
              data-testid="career-health-disclaimer"
            >
              {latest.disclaimer}
            </p>
            <p className="mt-2 text-xs text-muted">
              Snapshot created {formattedDateTime(latest.createdAt)} · Engine{" "}
              {latest.engineVersion}
              {latestDetail
                ? ` · Configuration ${latestDetail.configurationVersion}`
                : ""}
            </p>
          </section>

          {!latestDetail ? (
            <div className="rounded-xl border border-line p-4">
              <p className="text-sm text-muted">
                This history row is a bounded summary. Load its immutable detail
                only when you need components, findings, and formula metadata.
              </p>
              <Button
                className="mt-3"
                loading={busyKeys.has(`health-detail-${latest.id}`)}
                loadingLabel="Loading snapshot…"
                onClick={() => void onLoad(latest.id)}
                variant="secondary"
              >
                Load snapshot details
              </Button>
            </div>
          ) : (
            <>
              <section aria-labelledby="career-health-components">
                <h3
                  className="text-lg font-black"
                  id="career-health-components"
                >
                  Component calculation
                </h3>
                <div className="data-region table-scroll mt-3">
                  <table className="min-w-full divide-y divide-line text-left text-sm">
                    <caption className="sr-only">
                      Career Health component scores, weights, contributions,
                      and explanations
                    </caption>
                    <thead className="bg-surface-subtle text-xs uppercase tracking-wide text-muted">
                      <tr>
                        <th className="px-4 py-3" scope="col">
                          Component
                        </th>
                        <th className="px-4 py-3" scope="col">
                          Weight
                        </th>
                        <th className="px-4 py-3" scope="col">
                          Score
                        </th>
                        <th className="px-4 py-3" scope="col">
                          Contribution
                        </th>
                        <th className="px-4 py-3" scope="col">
                          Explanation
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {latestDetail.components.map((component) => (
                        <tr key={component.id}>
                          <th className="px-4 py-3 font-bold" scope="row">
                            {humanize(component.dimension)}
                          </th>
                          <td className="px-4 py-3">
                            {basisPoints(component.configuredWeightBasisPoints)}
                          </td>
                          <td className="px-4 py-3">
                            {component.applicable
                              ? basisPoints(component.scoreBasisPoints)
                              : "Not applicable"}
                          </td>
                          <td className="px-4 py-3">
                            {basisPoints(component.contributionBasisPoints)}
                          </td>
                          <td className="min-w-64 px-4 py-3 text-muted">
                            {component.explanation}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              <details className="rounded-xl border border-line p-4">
                <summary className="cursor-pointer font-extrabold">
                  Formula snapshot
                </summary>
                <p className="mt-2 text-xs leading-5 text-muted">
                  This is the versioned formula metadata stored with this
                  immutable calculation.
                </p>
                <div className="mt-3">
                  <FormulaSnapshot snapshot={latestDetail.formulaSnapshot} />
                </div>
              </details>

              <section aria-labelledby="career-health-findings">
                <h3 className="text-lg font-black" id="career-health-findings">
                  Findings
                </h3>
                {latestDetail.findings.length === 0 ? (
                  <p className="mt-2 text-sm text-muted">
                    No follow-up findings for this snapshot.
                  </p>
                ) : (
                  <ul className="mt-3 grid gap-2">
                    {latestDetail.findings.map((finding) => (
                      <li
                        className="rounded-xl border border-line p-3 text-sm"
                        key={finding.id}
                      >
                        <Badge
                          tone={
                            finding.severity === "attention"
                              ? "warning"
                              : "neutral"
                          }
                        >
                          {humanize(finding.severity)}
                        </Badge>
                        <p className="mt-2">{finding.message}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </>
          )}

          <details className="rounded-xl border border-line p-4">
            <summary className="cursor-pointer font-extrabold">
              Snapshot history ({analyses.length})
            </summary>
            <ul className="mt-3 grid gap-2">
              {orderedAnalyses.map((analysis) => (
                <li
                  className="flex flex-col gap-2 rounded-xl bg-surface-subtle p-3 text-sm sm:flex-row sm:items-center sm:justify-between"
                  key={analysis.id}
                >
                  <span>
                    {formattedDateTime(analysis.createdAt)} ·{" "}
                    {analysis.displayScore === null
                      ? "Insufficient data"
                      : `${analysis.displayScore}/100`}{" "}
                    · {humanize(analysis.label)}
                  </span>
                  <span className="flex flex-wrap gap-2">
                    {!isHealthDetail(analysis) && (
                      <Button
                        loading={busyKeys.has(`health-detail-${analysis.id}`)}
                        loadingLabel="Loading…"
                        onClick={() => void onLoad(analysis.id)}
                        variant="secondary"
                      >
                        Inspect
                      </Button>
                    )}
                    <Button
                      aria-label={`Delete Career Health snapshot from ${formattedDateTime(analysis.createdAt)}`}
                      onClick={() => onDelete(analysis)}
                      variant="ghost"
                    >
                      <Trash2 aria-hidden="true" className="size-4" />
                      Delete
                    </Button>
                  </span>
                </li>
              ))}
            </ul>
          </details>
        </div>
      )}
    </Card>
  );
}

function GrowthInsightsPanel({ insights }: { insights: CareerGrowthInsights }) {
  const promotion = insights.promotionReadiness;
  return (
    <section className="space-y-5" aria-labelledby="growth-insights-heading">
      <div className="flex items-center gap-3">
        <span
          aria-hidden="true"
          className="grid size-10 place-items-center rounded-xl bg-primary-soft text-primary"
        >
          <ShieldCheck className="size-5" />
        </span>
        <div>
          <h2 className="text-2xl font-black" id="growth-insights-heading">
            Achievement and promotion preparation
          </h2>
          <p className="text-sm text-muted">
            Live, owner-authorized views derived from currently eligible Career
            Record evidence.
          </p>
        </div>
      </div>

      <Card className="p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-primary">
              Promotion Readiness
            </p>
            <h3 className="mt-1 text-xl font-black">
              Evidence-backed preparation checklist
            </h3>
          </div>
          <Badge
            tone={
              promotion.status === "review_ready"
                ? "success"
                : promotion.status === "insufficient_evidence"
                  ? "warning"
                  : "primary"
            }
          >
            {humanize(promotion.status)}
          </Badge>
        </div>
        <p
          className="mt-3 max-w-4xl text-xs font-semibold leading-5 text-muted"
          data-testid="promotion-readiness-disclaimer"
        >
          {promotion.disclaimer}
        </p>
        <div className="data-region table-scroll mt-5">
          <table className="min-w-full divide-y divide-line text-left text-sm">
            <caption className="sr-only">
              Promotion preparation checks, evidence state, and next action
            </caption>
            <thead className="bg-surface-subtle text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-3" scope="col">
                  Preparation signal
                </th>
                <th className="px-4 py-3" scope="col">
                  State
                </th>
                <th className="px-4 py-3" scope="col">
                  Explanation
                </th>
                <th className="px-4 py-3" scope="col">
                  Evidence
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {promotion.checks.map((check) => (
                <tr key={check.code}>
                  <th className="px-4 py-3 font-bold" scope="row">
                    {check.label}
                  </th>
                  <td className="px-4 py-3">
                    <Badge
                      tone={
                        check.status === "supported"
                          ? "success"
                          : check.status === "needs_evidence"
                            ? "warning"
                            : "neutral"
                      }
                    >
                      {humanize(check.status)}
                    </Badge>
                  </td>
                  <td className="min-w-72 px-4 py-3 text-muted">
                    {check.explanation}
                  </td>
                  <td className="px-4 py-3">
                    {check.evidenceCount === 0
                      ? "None linked"
                      : `${check.evidenceCount} eligible`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card className="p-5">
          <h3 className="text-lg font-black">Achievement history</h3>
          <p className="mt-1 text-sm text-muted">
            Exact eligible Evidence Vault revisions, newest first.
          </p>
          {insights.achievements.length === 0 ? (
            <EmptyState
              className="mt-4"
              description="Confirm supported achievements in the Evidence Vault to build this history."
              title="No eligible achievements yet"
            />
          ) : (
            <ol className="mt-4 grid gap-3">
              {insights.achievements.map((item) => (
                <li
                  className="rounded-xl border border-line bg-surface-subtle p-4"
                  key={item.evidenceRevisionId}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="success">{humanize(item.strength)}</Badge>
                    <Badge>{humanize(item.evidenceType)}</Badge>
                    <span className="text-xs text-muted">
                      Revision {item.revisionNumber} ·{" "}
                      {formattedDateTime(item.revisedAt)}
                    </span>
                  </div>
                  <h4 className="mt-2 font-black">{item.title}</h4>
                  <p className="mt-1 text-sm leading-6">{item.statement}</p>
                  <Link
                    className="mt-3 inline-flex text-sm font-bold text-primary hover:underline"
                    href={`/evidence/${item.evidenceId}`}
                  >
                    Review exact evidence
                  </Link>
                </li>
              ))}
            </ol>
          )}
        </Card>

        <Card className="p-5">
          <h3 className="text-lg font-black">Skill-evidence dashboard</h3>
          <p className="mt-1 text-sm text-muted">
            A skill is demonstrated here only when current eligible evidence is
            linked.
          </p>
          {insights.skills.length === 0 ? (
            <EmptyState
              className="mt-4"
              description="Add skills to your Career Profile and connect eligible evidence."
              title="No documented skills yet"
            />
          ) : (
            <div className="data-region table-scroll mt-4">
              <table className="min-w-full divide-y divide-line text-left text-sm">
                <caption className="sr-only">
                  Documented skills and their eligible evidence coverage
                </caption>
                <thead className="bg-surface-subtle text-xs uppercase tracking-wide text-muted">
                  <tr>
                    <th className="px-4 py-3" scope="col">
                      Skill
                    </th>
                    <th className="px-4 py-3" scope="col">
                      Evidence
                    </th>
                    <th className="px-4 py-3" scope="col">
                      Latest
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {insights.skills.map((skill) => (
                    <tr key={skill.skillId}>
                      <th className="px-4 py-3" scope="row">
                        <span className="font-bold">{skill.name}</span>
                        <span className="block text-xs font-normal text-muted">
                          {skill.category ?? "Uncategorized"} ·{" "}
                          {skill.proficiency
                            ? humanize(skill.proficiency)
                            : "Proficiency not set"}
                        </span>
                      </th>
                      <td className="px-4 py-3">
                        {skill.evidenceCount === 0 ? (
                          <Badge tone="warning">Not demonstrated</Badge>
                        ) : (
                          <Badge tone="success">
                            {skill.evidenceCount} eligible
                          </Badge>
                        )}
                      </td>
                      <td className="px-4 py-3 text-muted">
                        {skill.latestEvidenceAt
                          ? formattedDateTime(skill.latestEvidenceAt)
                          : "No eligible evidence"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      <Card className="p-5">
        <h3 className="text-lg font-black">Annual resume refresh workflow</h3>
        <p className="mt-1 text-sm text-muted">
          Create an Annual resume refresh development item, move it through the
          explicit status controls, and link eligible evidence before marking it
          complete.
        </p>
        {insights.annualResumeRefreshes.length === 0 ? (
          <EmptyState
            className="mt-4"
            description="Use the Development plan form below and choose Annual resume refresh."
            title="No annual refresh scheduled"
          />
        ) : (
          <ul className="mt-4 grid gap-2 sm:grid-cols-2">
            {insights.annualResumeRefreshes.map((item) => (
              <li
                className="rounded-xl border border-line bg-surface-subtle p-4"
                key={item.id}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-black">{item.title}</span>
                  <Badge
                    tone={
                      item.status === "completed"
                        ? "success"
                        : item.status === "cancelled"
                          ? "neutral"
                          : "primary"
                    }
                  >
                    {humanize(item.status)}
                  </Badge>
                </div>
                <p className="mt-2 text-xs text-muted">
                  Target {formattedDate(item.targetDate)} ·{" "}
                  {item.evidenceLinks.length} eligible evidence link(s)
                </p>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </section>
  );
}

function confirmation(action: ConfirmAction | undefined): {
  confirmLabel: string;
  description: string;
  title: string;
} {
  if (!action) {
    return {
      confirmLabel: "Confirm",
      description: "",
      title: "Confirm action",
    };
  }
  switch (action.kind) {
    case "delete-goal":
      return {
        confirmLabel: "Delete goal",
        description: `Delete “${action.goal.title}” and its milestones? This cannot be undone.`,
        title: "Delete career goal?",
      };
    case "delete-milestone":
      return {
        confirmLabel: "Delete milestone",
        description: `Delete “${action.milestone.title}”? This cannot be undone.`,
        title: "Delete milestone?",
      };
    case "delete-development":
      return {
        confirmLabel: "Delete plan item",
        description: `Delete “${action.item.title}”? This cannot be undone.`,
        title: "Delete development plan item?",
      };
    case "delete-review":
      return {
        confirmLabel: "Delete review",
        description: `Delete “${action.review.currentVersion.title}” and all of its immutable versions? This cannot be undone.`,
        title: "Delete career review?",
      };
    case "finalize-review":
      return {
        confirmLabel: "Finalize review",
        description:
          "Finalizing preserves this version as immutable. Future changes must be made as a new revision.",
        title: "Finalize this review version?",
      };
    case "revise-review":
      return {
        confirmLabel: "Create revision",
        description:
          "This creates a new immutable version and keeps the current version in history.",
        title: "Create a new review revision?",
      };
    case "delete-health":
      return {
        confirmLabel: "Delete snapshot",
        description:
          "Delete this Career Health snapshot? Other goals and career records are not changed.",
        title: "Delete Career Health snapshot?",
      };
  }
}

function confirmationBusyKey(action: ConfirmAction): string {
  switch (action.kind) {
    case "delete-goal":
      return `confirm-delete-goal-${action.goal.id}`;
    case "delete-milestone":
      return `confirm-delete-milestone-${action.milestone.id}`;
    case "delete-development":
      return `confirm-delete-development-${action.item.id}`;
    case "delete-review":
      return `confirm-delete-review-${action.review.id}`;
    case "finalize-review":
      return `confirm-finalize-review-${action.review.id}`;
    case "revise-review":
      return `confirm-revise-review-${action.review.id}`;
    case "delete-health":
      return `confirm-delete-health-${action.analysis.id}`;
  }
}

export function CareerGrowthView() {
  const [data, setData] = useState<GrowthData>();
  const [loading, setLoading] = useState(true);
  const [loadFailure, setLoadFailure] = useState<string>();
  const [actionFailure, setActionFailure] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const [conflict, setConflict] = useState(false);
  const [busyKeys, setBusyKeys] = useState<ReadonlySet<string>>(
    () => new Set(),
  );
  const [confirmAction, setConfirmAction] = useState<ConfirmAction>();
  const requestEpoch = useRef(0);
  const loadController = useRef<AbortController | undefined>(undefined);
  const pageControllers = useRef(new Map<GrowthCollection, AbortController>());
  const busyKeysRef = useRef(new Set<string>());
  const intentKeys = useRef(
    new Map<string, { idempotencyKey: string; signature: string }>(),
  );

  const stableIntent = useCallback((key: string, payload: unknown) => {
    const signature = payloadSignature(payload);
    const existing = intentKeys.current.get(key);
    if (existing?.signature === signature) return existing.idempotencyKey;
    const created = intentKey(key);
    intentKeys.current.set(key, { idempotencyKey: created, signature });
    return created;
  }, []);

  const clearIntent = useCallback((key: string) => {
    intentKeys.current.delete(key);
  }, []);

  const load = useCallback(async () => {
    loadController.current?.abort();
    for (const activeController of pageControllers.current.values()) {
      activeController.abort();
    }
    pageControllers.current.clear();
    const controller = new AbortController();
    loadController.current = controller;
    const epoch = ++requestEpoch.current;
    setLoading(true);
    setLoadFailure(undefined);
    setActionFailure(undefined);
    setConflict(false);
    try {
      const [goals, developmentItems, reviews, health, insights] =
        await Promise.all([
          listGoals({ signal: controller.signal }),
          listDevelopmentItems({ signal: controller.signal }),
          listCareerReviews({ signal: controller.signal }),
          listCareerHealth({ signal: controller.signal }),
          getCareerGrowthInsights(controller.signal),
        ]);
      if (epoch !== requestEpoch.current || controller.signal.aborted) return;
      setData({
        developmentCursor: developmentItems.page.nextCursor,
        developmentItems: developmentItems.data,
        goalCursor: goals.page.nextCursor,
        goals: goals.data,
        healthCursor: health.page.nextCursor,
        health: health.data,
        insights,
        reviewCursor: reviews.page.nextCursor,
        reviews: reviews.data,
      });
    } catch (error) {
      if (
        epoch !== requestEpoch.current ||
        controller.signal.aborted ||
        isAbortError(error)
      ) {
        return;
      }
      setLoadFailure(
        requestErrorMessage(error, "Career Growth could not be loaded."),
      );
    } finally {
      if (epoch === requestEpoch.current && !controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const activePageControllers = pageControllers.current;
    queueMicrotask(() => void load());
    return () => {
      requestEpoch.current += 1;
      loadController.current?.abort();
      for (const activeController of activePageControllers.values()) {
        activeController.abort();
      }
      activePageControllers.clear();
    };
  }, [load]);

  function reportError(error: unknown, fallback: string) {
    const stale = isVersionConflict(error);
    setConflict(stale);
    setSuccess(undefined);
    setActionFailure(
      stale
        ? "This record changed in another session. Reload authoritative data before trying again."
        : requestErrorMessage(error, fallback),
    );
  }

  function beginAction(key: string): boolean {
    if (busyKeysRef.current.has(key)) return false;
    busyKeysRef.current.add(key);
    setBusyKeys(new Set(busyKeysRef.current));
    setActionFailure(undefined);
    setSuccess(undefined);
    setConflict(false);
    return true;
  }

  function endAction(key: string) {
    busyKeysRef.current.delete(key);
    setBusyKeys(new Set(busyKeysRef.current));
  }

  async function refreshInsights() {
    const epoch = requestEpoch.current;
    try {
      const insights = await getCareerGrowthInsights();
      if (epoch !== requestEpoch.current) return;
      setData((current) => (current ? { ...current, insights } : current));
    } catch (error) {
      if (epoch !== requestEpoch.current || isAbortError(error)) return;
      setLoadFailure(
        requestErrorMessage(
          error,
          "Achievement, skill-evidence, and promotion insights could not be refreshed.",
        ),
      );
    }
  }

  function finishAction(message: string, key: string) {
    setSuccess(message);
    setActionFailure(undefined);
    setConflict(false);
    endAction(key);
    queueMicrotask(() => void refreshInsights());
  }

  async function loadMore(collection: GrowthCollection) {
    if (!data) return;
    const cursor =
      collection === "goals"
        ? data.goalCursor
        : collection === "development"
          ? data.developmentCursor
          : collection === "reviews"
            ? data.reviewCursor
            : data.healthCursor;
    if (!cursor) return;
    const key = `more-${collection}`;
    pageControllers.current.get(collection)?.abort();
    const controller = new AbortController();
    pageControllers.current.set(collection, controller);
    if (!beginAction(key)) return;
    try {
      if (collection === "goals") {
        const page = await listGoals({ cursor, signal: controller.signal });
        if (controller.signal.aborted) return;
        setData((current) =>
          current
            ? {
                ...current,
                goalCursor: page.page.nextCursor,
                goals: appendUnique(current.goals, page.data),
              }
            : current,
        );
      } else if (collection === "development") {
        const page = await listDevelopmentItems({
          cursor,
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        setData((current) =>
          current
            ? {
                ...current,
                developmentCursor: page.page.nextCursor,
                developmentItems: appendUnique(
                  current.developmentItems,
                  page.data,
                ),
              }
            : current,
        );
      } else if (collection === "reviews") {
        const page = await listCareerReviews({
          cursor,
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        setData((current) =>
          current
            ? {
                ...current,
                reviewCursor: page.page.nextCursor,
                reviews: appendUnique(current.reviews, page.data),
              }
            : current,
        );
      } else {
        const page = await listCareerHealth({
          cursor,
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        setData((current) =>
          current
            ? {
                ...current,
                health: appendUnique(current.health, page.data),
                healthCursor: page.page.nextCursor,
              }
            : current,
        );
      }
      finishAction(`More ${humanize(collection)} records loaded.`, key);
    } catch (error) {
      if (!controller.signal.aborted && !isAbortError(error)) {
        reportError(
          error,
          `More ${humanize(collection)} records could not be loaded.`,
        );
      }
    } finally {
      if (pageControllers.current.get(collection) === controller) {
        pageControllers.current.delete(collection);
      }
      endAction(key);
    }
  }

  async function loadGoalDetail(goalId: string) {
    const key = `goal-detail-${goalId}`;
    if (!beginAction(key)) return;
    try {
      const detail = await getGoal(goalId);
      setData((current) =>
        current
          ? {
              ...current,
              goals: current.goals.map((item) =>
                item.id === detail.id ? detail : item,
              ),
            }
          : current,
      );
    } catch (error) {
      reportError(error, "The goal details could not be loaded.");
    } finally {
      endAction(key);
    }
  }

  async function loadReviewDetail(reviewId: string) {
    const key = `review-detail-${reviewId}`;
    if (!beginAction(key)) return;
    try {
      const detail = await getCareerReview(reviewId);
      setData((current) =>
        current
          ? {
              ...current,
              reviews: current.reviews.map((item) =>
                item.id === detail.id ? detail : item,
              ),
            }
          : current,
      );
    } catch (error) {
      reportError(error, "The review details could not be loaded.");
    } finally {
      endAction(key);
    }
  }

  async function loadHealthDetail(analysisId: string) {
    const key = `health-detail-${analysisId}`;
    if (!beginAction(key)) return;
    try {
      const detail = await getCareerHealth(analysisId);
      setData((current) =>
        current
          ? {
              ...current,
              health: current.health.map((item) =>
                item.id === detail.id ? detail : item,
              ),
            }
          : current,
      );
    } catch (error) {
      reportError(error, "The Career Health details could not be loaded.");
    } finally {
      endAction(key);
    }
  }

  async function addGoal(input: GoalCreateInput): Promise<boolean> {
    const key = "goal-new";
    if (!beginAction(key)) return false;
    try {
      const created = await createGoal(input, stableIntent(key, input));
      setData((current) =>
        current
          ? { ...current, goals: prependUnique(current.goals, created) }
          : current,
      );
      clearIntent(key);
      finishAction(`${created.title} added as a career goal.`, key);
      return true;
    } catch (error) {
      reportError(error, "The goal could not be added.");
      endAction(key);
      return false;
    }
  }

  async function saveGoal(goal: Goal, input: GoalUpdateInput) {
    const key = `goal-${goal.id}`;
    if (!beginAction(key)) return;
    try {
      const updated = await updateGoal(goal, input);
      setData((current) =>
        current
          ? {
              ...current,
              goals: current.goals.map((item) =>
                item.id === updated.id ? updated : item,
              ),
            }
          : current,
      );
      finishAction(`${updated.title} updated.`, key);
    } catch (error) {
      reportError(error, "The goal could not be updated.");
      endAction(key);
    }
  }

  async function addMilestone(
    goal: Goal,
    input: MilestoneCreateInput,
  ): Promise<boolean> {
    const key = `milestone-new-${goal.id}`;
    if (!beginAction(key)) return false;
    try {
      const created = await createMilestone(
        goal.id,
        input,
        stableIntent(key, { goalId: goal.id, ...input }),
      );
      setData((current) =>
        current
          ? {
              ...current,
              goals: current.goals.map((item) =>
                item.id === goal.id && isGoalDetail(item)
                  ? {
                      ...item,
                      milestones: appendUnique(item.milestones, [created]),
                    }
                  : item,
              ),
            }
          : current,
      );
      clearIntent(key);
      finishAction(`${created.title} added as a milestone.`, key);
      return true;
    } catch (error) {
      reportError(error, "The milestone could not be added.");
      endAction(key);
      return false;
    }
  }

  async function saveMilestone(
    milestone: GoalMilestone,
    input: MilestoneUpdateInput,
  ) {
    const key = `milestone-${milestone.id}`;
    if (!beginAction(key)) return;
    try {
      const updated = await updateMilestone(milestone, input);
      setData((current) =>
        current
          ? {
              ...current,
              goals: current.goals.map((goal) =>
                goal.id === updated.goalId && isGoalDetail(goal)
                  ? {
                      ...goal,
                      milestones: goal.milestones.map((item) =>
                        item.id === updated.id ? updated : item,
                      ),
                    }
                  : goal,
              ),
            }
          : current,
      );
      finishAction(`${updated.title} milestone updated.`, key);
    } catch (error) {
      reportError(error, "The milestone could not be updated.");
      endAction(key);
    }
  }

  async function addDevelopment(
    input: DevelopmentItemCreateInput,
  ): Promise<boolean> {
    const key = "development-new";
    if (!beginAction(key)) return false;
    try {
      const created = await createDevelopmentItem(
        input,
        stableIntent(key, input),
      );
      setData((current) =>
        current
          ? {
              ...current,
              developmentItems: prependUnique(
                current.developmentItems,
                created,
              ),
            }
          : current,
      );
      clearIntent(key);
      finishAction(`${created.title} added to your development plan.`, key);
      return true;
    } catch (error) {
      reportError(error, "The development plan item could not be added.");
      endAction(key);
      return false;
    }
  }

  async function saveDevelopment(
    item: DevelopmentItem,
    input: DevelopmentItemUpdateInput,
  ) {
    const key = `development-${item.id}`;
    if (!beginAction(key)) return;
    try {
      const updated = await updateDevelopmentItem(item, input);
      setData((current) =>
        current
          ? {
              ...current,
              developmentItems: current.developmentItems.map((entry) =>
                entry.id === updated.id ? updated : entry,
              ),
            }
          : current,
      );
      finishAction(`${updated.title} updated.`, key);
    } catch (error) {
      reportError(error, "The development plan item could not be updated.");
      endAction(key);
    }
  }

  async function addReview(input: CareerReviewCreateInput): Promise<boolean> {
    const key = "review-new";
    if (!beginAction(key)) return false;
    try {
      const created = await createCareerReview(input, stableIntent(key, input));
      setData((current) =>
        current
          ? { ...current, reviews: prependUnique(current.reviews, created) }
          : current,
      );
      clearIntent(key);
      finishAction(`${created.currentVersion.title} started as a draft.`, key);
      return true;
    } catch (error) {
      reportError(error, "The career review could not be started.");
      endAction(key);
      return false;
    }
  }

  async function analyzeHealth() {
    const key = "health-analyze";
    if (!beginAction(key)) return;
    try {
      const created = await analyzeCareerHealth(stableIntent(key, {}));
      setData((current) =>
        current
          ? { ...current, health: prependUnique(current.health, created) }
          : current,
      );
      clearIntent(key);
      finishAction(
        created.status === "complete"
          ? "Career Health recalculated."
          : "Career Health checked; more data is needed for a score.",
        key,
      );
    } catch (error) {
      reportError(error, "Career Health could not be calculated.");
      endAction(key);
    }
  }

  async function confirm() {
    const action = confirmAction;
    if (!action) return;
    const key = confirmationBusyKey(action);
    if (!beginAction(key)) return;
    try {
      switch (action.kind) {
        case "delete-goal":
          await deleteGoal(action.goal);
          setData((current) =>
            current
              ? {
                  ...current,
                  goals: current.goals.filter(
                    (item) => item.id !== action.goal.id,
                  ),
                }
              : current,
          );
          finishAction(`${action.goal.title} deleted.`, key);
          break;
        case "delete-milestone":
          await deleteMilestone(action.milestone);
          setData((current) =>
            current
              ? {
                  ...current,
                  goals: current.goals.map((goal) =>
                    goal.id === action.milestone.goalId && isGoalDetail(goal)
                      ? {
                          ...goal,
                          milestones: goal.milestones.filter(
                            (item) => item.id !== action.milestone.id,
                          ),
                        }
                      : goal,
                  ),
                }
              : current,
          );
          finishAction(`${action.milestone.title} deleted.`, key);
          break;
        case "delete-development":
          await deleteDevelopmentItem(action.item);
          setData((current) =>
            current
              ? {
                  ...current,
                  developmentItems: current.developmentItems.filter(
                    (item) => item.id !== action.item.id,
                  ),
                }
              : current,
          );
          finishAction(`${action.item.title} deleted.`, key);
          break;
        case "delete-review":
          await deleteCareerReview(action.review);
          setData((current) =>
            current
              ? {
                  ...current,
                  reviews: current.reviews.filter(
                    (item) => item.id !== action.review.id,
                  ),
                }
              : current,
          );
          finishAction(`${action.review.currentVersion.title} deleted.`, key);
          break;
        case "finalize-review": {
          const intent = key;
          const updated = await finalizeCareerReview(
            action.review,
            stableIntent(intent, {
              reviewId: action.review.id,
              version: action.review.version,
            }),
          );
          setData((current) =>
            current
              ? {
                  ...current,
                  reviews: current.reviews.map((item) =>
                    item.id === updated.id ? updated : item,
                  ),
                }
              : current,
          );
          clearIntent(intent);
          finishAction(`${updated.currentVersion.title} finalized.`, key);
          break;
        }
        case "revise-review": {
          const updated = await reviseCareerReview(action.review, action.input);
          setData((current) =>
            current
              ? {
                  ...current,
                  reviews: current.reviews.map((item) =>
                    item.id === updated.id ? updated : item,
                  ),
                }
              : current,
          );
          finishAction(
            `Version ${updated.latestVersionNumber} created without changing earlier versions.`,
            key,
          );
          break;
        }
        case "delete-health":
          await deleteCareerHealth(action.analysis);
          setData((current) =>
            current
              ? {
                  ...current,
                  health: current.health.filter(
                    (item) => item.id !== action.analysis.id,
                  ),
                }
              : current,
          );
          finishAction("Career Health snapshot deleted.", key);
          break;
      }
      setConfirmAction(undefined);
    } catch (error) {
      setConfirmAction(undefined);
      reportError(error, "The confirmed action could not be completed.");
      endAction(key);
    }
  }

  if (!data && loadFailure && !loading) {
    return (
      <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
        <ErrorState
          description={loadFailure}
          onRetry={() => void load()}
          title="Career Growth unavailable"
        />
      </main>
    );
  }

  if (!data || loading) return <CareerGrowthLoading />;

  const confirmationCopy = confirmation(confirmAction);

  return (
    <main
      className="mx-auto max-w-7xl space-y-8 p-4 sm:p-6 lg:p-8"
      id="main-content"
    >
      <PageHeader
        actions={
          <Button onClick={() => void load()} variant="secondary">
            <RefreshCcw aria-hidden="true" className="size-4" />
            Reload data
          </Button>
        }
        description="Plan goals, record milestone progress, attach revision-specific evidence, preserve review history, and inspect every Career Health input."
        eyebrow="Long-term growth"
        title="Career Growth"
      />

      {loadFailure && (
        <Alert title="Reload failed" tone="danger">
          <p>{loadFailure}</p>
          <Button
            className="mt-3"
            onClick={() => void load()}
            variant="secondary"
          >
            Try reload again
          </Button>
        </Alert>
      )}
      {success && (
        <Alert title="Saved" tone="success">
          <p role="status">{success}</p>
        </Alert>
      )}
      {actionFailure && (
        <Alert
          title={conflict ? "Authoritative reload required" : "Action failed"}
          tone="danger"
        >
          <p>{actionFailure}</p>
          {conflict && (
            <Button
              className="mt-3"
              onClick={() => void load()}
              variant="secondary"
            >
              Reload authoritative data
            </Button>
          )}
        </Alert>
      )}

      <GrowthInsightsPanel insights={data.insights} />

      <CareerHealthPanel
        analyses={data.health}
        busyKeys={busyKeys}
        onAnalyze={analyzeHealth}
        onDelete={(analysis) =>
          setConfirmAction({ analysis, kind: "delete-health" })
        }
        onLoad={loadHealthDetail}
      />
      {data.healthCursor && (
        <div className="flex justify-center">
          <Button
            loading={busyKeys.has("more-health")}
            loadingLabel="Loading snapshots…"
            onClick={() => void loadMore("health")}
            variant="secondary"
          >
            Load more Career Health snapshots
          </Button>
        </div>
      )}

      <section className="space-y-4" aria-labelledby="career-goals-heading">
        <div className="flex items-center gap-3">
          <span
            aria-hidden="true"
            className="grid size-10 place-items-center rounded-xl bg-primary-soft text-primary"
          >
            <Flag className="size-5" />
          </span>
          <div>
            <h2 className="text-2xl font-black" id="career-goals-heading">
              Goals and milestones
            </h2>
            <p className="text-sm text-muted">
              Every update is explicit; milestones always have a non-drag status
              control.
            </p>
          </div>
        </div>
        <GoalCreateForm busy={busyKeys.has("goal-new")} onCreate={addGoal} />
        {data.goals.length === 0 ? (
          <EmptyState
            description="Add your first outcome and break it into evidence-backed milestones."
            title="No career goals yet"
          />
        ) : (
          <div className="grid gap-4">
            {data.goals.map((goal) =>
              isGoalDetail(goal) ? (
                <GoalCard
                  busyKeys={busyKeys}
                  goal={goal}
                  key={goal.id}
                  onDelete={(item) =>
                    setConfirmAction({ goal: item, kind: "delete-goal" })
                  }
                  onDeleteMilestone={(milestone) =>
                    setConfirmAction({
                      kind: "delete-milestone",
                      milestone,
                    })
                  }
                  onMilestoneCreate={addMilestone}
                  onMilestoneUpdate={saveMilestone}
                  onUpdate={saveGoal}
                />
              ) : (
                <GoalSummaryCard
                  busy={busyKeys.has(`goal-detail-${goal.id}`)}
                  goal={goal}
                  key={goal.id}
                  onLoad={loadGoalDetail}
                />
              ),
            )}
          </div>
        )}
        {data.goalCursor && (
          <div className="flex justify-center">
            <Button
              loading={busyKeys.has("more-goals")}
              loadingLabel="Loading goals…"
              onClick={() => void loadMore("goals")}
              variant="secondary"
            >
              Load more goals
            </Button>
          </div>
        )}
      </section>

      <section className="space-y-4" aria-labelledby="development-heading">
        <div className="flex items-center gap-3">
          <span
            aria-hidden="true"
            className="grid size-10 place-items-center rounded-xl bg-primary-soft text-primary"
          >
            <BookOpenCheck className="size-5" />
          </span>
          <div>
            <h2 className="text-2xl font-black" id="development-heading">
              Development plan
            </h2>
            <p className="text-sm text-muted">
              Track learning, credentials, reviews, promotion work, and internal
              mobility, including an evidence-backed annual resume refresh.
            </p>
          </div>
        </div>
        <DevelopmentCreateForm
          busy={busyKeys.has("development-new")}
          onCreate={addDevelopment}
        />
        {data.developmentItems.length === 0 ? (
          <EmptyState
            description="Add a focused learning or advancement item and link the evidence that demonstrates progress."
            title="No development plan items yet"
          />
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {data.developmentItems.map((item) => (
              <DevelopmentCard
                busy={busyKeys.has(`development-${item.id}`)}
                item={item}
                key={item.id}
                onDelete={(entry) =>
                  setConfirmAction({
                    item: entry,
                    kind: "delete-development",
                  })
                }
                onUpdate={saveDevelopment}
              />
            ))}
          </div>
        )}
        {data.developmentCursor && (
          <div className="flex justify-center">
            <Button
              loading={busyKeys.has("more-development")}
              loadingLabel="Loading plan items…"
              onClick={() => void loadMore("development")}
              variant="secondary"
            >
              Load more development items
            </Button>
          </div>
        )}
      </section>

      <section className="space-y-4" aria-labelledby="reviews-heading">
        <div className="flex items-center gap-3">
          <span
            aria-hidden="true"
            className="grid size-10 place-items-center rounded-xl bg-primary-soft text-primary"
          >
            <CalendarCheck className="size-5" />
          </span>
          <div>
            <h2 className="text-2xl font-black" id="reviews-heading">
              Career reviews
            </h2>
            <p className="text-sm text-muted">
              Finalized versions remain immutable; revisions explain what
              changed and preserve the complete history.
            </p>
          </div>
        </div>
        <ReviewCreateForm
          busy={busyKeys.has("review-new")}
          onCreate={addReview}
        />
        {data.reviews.length === 0 ? (
          <EmptyState
            description="Start a quarterly or annual review to preserve achievements, growth areas, and next focus."
            title="No career reviews yet"
          />
        ) : (
          <div className="grid gap-4">
            {data.reviews.map((review) =>
              isReviewDetail(review) ? (
                <ReviewCard
                  busyKeys={busyKeys}
                  key={review.id}
                  onDelete={(item) =>
                    setConfirmAction({ kind: "delete-review", review: item })
                  }
                  onFinalize={(item) =>
                    setConfirmAction({
                      kind: "finalize-review",
                      review: item,
                    })
                  }
                  onRevise={(item, input) =>
                    setConfirmAction({
                      input,
                      kind: "revise-review",
                      review: item,
                    })
                  }
                  review={review}
                />
              ) : (
                <ReviewSummaryCard
                  busy={busyKeys.has(`review-detail-${review.id}`)}
                  key={review.id}
                  onLoad={loadReviewDetail}
                  review={review}
                />
              ),
            )}
          </div>
        )}
        {data.reviewCursor && (
          <div className="flex justify-center">
            <Button
              loading={busyKeys.has("more-reviews")}
              loadingLabel="Loading reviews…"
              onClick={() => void loadMore("reviews")}
              variant="secondary"
            >
              Load more reviews
            </Button>
          </div>
        )}
      </section>

      <aside className="rounded-2xl border border-line bg-surface-subtle p-5 text-sm leading-6 text-muted">
        <div className="flex items-start gap-3">
          <History aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
          <p>
            Career records and evidence remain the source of truth. This
            workspace records planning and derived maintenance signals; it never
            silently rewrites a published career document.
          </p>
        </div>
      </aside>

      <ConfirmDialog
        confirmLabel={confirmationCopy.confirmLabel}
        description={confirmationCopy.description}
        loading={[...busyKeys].some((key) => key.startsWith("confirm-"))}
        onConfirm={() => void confirm()}
        onOpenChange={(open) => {
          if (
            !open &&
            ![...busyKeys].some((key) => key.startsWith("confirm-"))
          ) {
            setConfirmAction(undefined);
          }
        }}
        open={Boolean(confirmAction)}
        title={confirmationCopy.title}
      />
    </main>
  );
}

export function CareerGrowthLoading() {
  return (
    <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
      <LoadingSkeleton />
    </main>
  );
}

export function CareerGrowthRouteError({ reset }: { reset: () => void }) {
  return (
    <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
      <ErrorState
        description="The Career Growth route could not be rendered. Your records were not changed."
        onRetry={reset}
        title="Career Growth unavailable"
      />
    </main>
  );
}
