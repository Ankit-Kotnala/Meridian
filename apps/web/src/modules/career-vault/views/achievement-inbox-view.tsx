"use client";

import { Award, Pencil, Plus, RefreshCcw, Trash2 } from "lucide-react";
import Link from "next/link";
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
  Card,
  CheckboxField,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  FieldLabel,
  LoadingSkeleton,
  Select,
  TextField,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  ApiRequestError,
  convertAchievement,
  createAchievement,
  deleteAchievement,
  getAchievements,
  getCareerItems,
  getExperiences,
  getReminderPreferences,
  updateAchievement,
  updateReminderPreferences,
} from "../api/career-vault-api";
import type {
  Achievement,
  AchievementInput,
  CareerItem,
  Experience,
  Page,
  ReminderPreferences,
} from "../api/types";
import { FieldErrorSummary, TextareaField } from "../components/form-controls";
import {
  type FieldErrors,
  validateAchievementConversion,
  validateAchievementDraft,
} from "../validation/career-vault-validation";

const questions = [
  ["delivered", "What did you deliver?"],
  ["problem", "What problem did it address?"],
  ["changed", "What changed as a result?"],
  ["affected", "Who or what was affected?"],
  ["measurement", "How was the result measured?"],
  ["collaboration", "Who did you collaborate with?"],
  ["methods", "What methods or tools did you use?"],
] as const;

function optional(form: FormData, name: string): string | null {
  return String(form.get(name) ?? "").trim() || null;
}

function AchievementEditor({
  errors,
  experiences,
  initial,
  loading,
  mode,
  onCancel,
  onSubmit,
  projects,
  setMode,
}: {
  errors: FieldErrors;
  experiences: Experience[];
  initial?: Achievement;
  loading: boolean;
  mode: "guided" | "quick";
  onCancel: () => void;
  onSubmit: (input: AchievementInput) => void;
  projects: CareerItem[];
  setMode: (mode: "guided" | "quick") => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const answers = Object.fromEntries(
      questions.map(([key]) => [key, String(form.get(key) ?? "").trim()]),
    ) as AchievementInput["answers"];
    const metric = {
      attribution: String(form.get("metricAttribution") ?? "individual") as
        "individual" | "shared" | "team",
      baseline: optional(form, "metricBaseline"),
      comparator: optional(form, "metricComparator"),
      name: String(form.get("metricName") ?? "").trim(),
      periodEnd: optional(form, "metricPeriodEnd"),
      periodStart: String(form.get("metricPeriodStart") ?? "").trim(),
      precision: String(form.get("metricPrecision") ?? "exact") as
        "approximate" | "exact",
      unit: String(form.get("metricUnit") ?? "").trim(),
      value: String(form.get("metricValue") ?? "").trim(),
    };
    const hasMetric = Boolean(
      metric.name ||
      metric.value ||
      metric.unit ||
      metric.periodStart ||
      metric.baseline ||
      metric.comparator,
    );
    onSubmit({
      answers,
      employerId: optional(form, "employerId"),
      metric: hasMetric ? metric : null,
      projectId: optional(form, "projectId"),
      title: String(form.get("title") ?? "").trim(),
    });
  }

  const visibleQuestions = mode === "quick" ? questions.slice(0, 3) : questions;
  return (
    <form className="space-y-5" onSubmit={submit}>
      <div
        className="flex flex-wrap gap-2"
        role="group"
        aria-label="Capture mode"
      >
        <Button
          aria-pressed={mode === "quick"}
          onClick={() => setMode("quick")}
          variant={mode === "quick" ? "primary" : "secondary"}
        >
          Quick capture
        </Button>
        <Button
          aria-pressed={mode === "guided"}
          onClick={() => setMode("guided")}
          variant={mode === "guided" ? "primary" : "secondary"}
        >
          Guided capture
        </Button>
      </div>
      <p className="text-sm text-muted">
        Unanswered prompts remain explicitly “Not answered”; Rezumi never fills
        missing facts.
      </p>
      <TextField
        defaultValue={initial?.title ?? ""}
        error={errors.title}
        id="achievement-title"
        label="Draft title"
        maxLength={300}
        name="title"
        required
      />
      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-2">
          <FieldLabel htmlFor="achievement-employer">
            Related experience (optional)
          </FieldLabel>
          <Select
            defaultValue={initial?.employerId ?? ""}
            id="achievement-employer"
            name="employerId"
          >
            <option value="">Not connected</option>
            {experiences.map((experience) => (
              <option key={experience.id} value={experience.id}>
                {experience.displayTitle || experience.officialTitle} at{" "}
                {experience.employer}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-2">
          <FieldLabel htmlFor="achievement-project">
            Related project (optional)
          </FieldLabel>
          <Select
            defaultValue={initial?.projectId ?? ""}
            id="achievement-project"
            name="projectId"
          >
            <option value="">Not connected</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.title}
              </option>
            ))}
          </Select>
        </div>
      </div>
      {visibleQuestions.map(([key, label]) => (
        <TextareaField
          defaultValue={initial?.answers[key] ?? ""}
          error={errors[key]}
          id={`achievement-${key}`}
          key={key}
          label={label}
          maxLength={2_000}
          name={key}
        />
      ))}
      {mode === "quick" &&
        questions
          .slice(3)
          .map(([key]) => (
            <input
              key={key}
              name={key}
              type="hidden"
              value={initial?.answers[key] ?? ""}
            />
          ))}

      <fieldset className="rounded-2xl border border-line p-4 sm:p-5">
        <legend className="px-2 text-sm font-extrabold">
          Measured result (optional)
        </legend>
        <p className="mb-4 text-xs leading-5 text-muted">
          If you enter any metric field, complete the measured result before
          saving.
        </p>
        <div className="grid gap-5 sm:grid-cols-2">
          <TextField
            defaultValue={initial?.metric?.name ?? ""}
            error={errors.metricName}
            id="achievement-metric-name"
            label="Result measured"
            maxLength={160}
            name="metricName"
          />
          <TextField
            defaultValue={initial?.metric?.value ?? ""}
            error={errors.metricValue}
            id="achievement-metric-value"
            label="Value"
            name="metricValue"
          />
          <TextField
            defaultValue={initial?.metric?.unit ?? ""}
            error={errors.metricUnit}
            id="achievement-metric-unit"
            label="Unit"
            maxLength={80}
            name="metricUnit"
          />
          <TextField
            defaultValue={initial?.metric?.periodStart ?? ""}
            error={errors.metricPeriodStart}
            id="achievement-metric-period-start"
            label="Period start"
            name="metricPeriodStart"
            type="month"
          />
          <TextField
            defaultValue={initial?.metric?.periodEnd ?? ""}
            error={errors.metricPeriodEnd}
            id="achievement-metric-period-end"
            label="Period end (optional)"
            name="metricPeriodEnd"
            type="month"
          />
          <TextField
            defaultValue={initial?.metric?.baseline ?? ""}
            error={errors.metricBaseline}
            id="achievement-metric-baseline"
            label="Baseline (optional)"
            maxLength={500}
            name="metricBaseline"
          />
          <TextField
            defaultValue={initial?.metric?.comparator ?? ""}
            id="achievement-metric-comparator"
            label="Comparator (optional)"
            maxLength={240}
            name="metricComparator"
          />
          <div className="space-y-2">
            <FieldLabel htmlFor="achievement-metric-precision">
              Precision
            </FieldLabel>
            <Select
              defaultValue={initial?.metric?.precision ?? "exact"}
              id="achievement-metric-precision"
              name="metricPrecision"
            >
              <option value="exact">Exact</option>
              <option value="approximate">Approximate</option>
            </Select>
          </div>
          <div className="space-y-2">
            <FieldLabel htmlFor="achievement-metric-attribution">
              Attribution
            </FieldLabel>
            <Select
              defaultValue={initial?.metric?.attribution ?? "individual"}
              id="achievement-metric-attribution"
              name="metricAttribution"
            >
              <option value="individual">Individual</option>
              <option value="team">Team</option>
              <option value="shared">Shared</option>
            </Select>
          </div>
        </div>
      </fieldset>
      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <Button disabled={loading} onClick={onCancel} variant="secondary">
          Cancel
        </Button>
        <Button loading={loading} loadingLabel="Saving draft…" type="submit">
          Save draft
        </Button>
      </div>
    </form>
  );
}

export function AchievementInboxView() {
  const [page, setPage] = useState<Page<Achievement>>();
  const [experiences, setExperiences] = useState<Experience[]>([]);
  const [projects, setProjects] = useState<CareerItem[]>([]);
  const [reminders, setReminders] = useState<ReminderPreferences>();
  const [editing, setEditing] = useState<Achievement | "new">();
  const [mode, setMode] = useState<"guided" | "quick">("quick");
  const [pendingConvert, setPendingConvert] = useState<Achievement>();
  const [pendingDelete, setPendingDelete] = useState<Achievement>();
  const [errors, setErrors] = useState<FieldErrors>({});
  const [failure, setFailure] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [loading, setLoading] = useState(false);
  const errorRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    setFailure(undefined);
    try {
      const [nextPage, nextExperiences, nextItems, nextReminders] =
        await Promise.all([
          getAchievements(),
          getExperiences({ includeProvenance: false }),
          getCareerItems(),
          getReminderPreferences(),
        ]);
      setPage(nextPage);
      setExperiences(nextExperiences);
      setProjects(nextItems.filter((item) => item.kind === "project"));
      setReminders(nextReminders);
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "We couldn’t load Achievement Inbox."),
      );
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  async function save(input: AchievementInput) {
    const nextErrors = validateAchievementDraft(input);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      queueMicrotask(() => errorRef.current?.focus());
      return;
    }
    setLoading(true);
    setFailure(undefined);
    setNotice(undefined);
    try {
      const saved =
        editing === "new" || !editing
          ? await createAchievement(input)
          : await updateAchievement(editing, input);
      setPage((current) =>
        current
          ? {
              ...current,
              data: current.data.some((item) => item.id === saved.id)
                ? current.data.map((item) =>
                    item.id === saved.id ? saved : item,
                  )
                : [saved, ...current.data],
            }
          : current,
      );
      setEditing(undefined);
      setErrors({});
      setNotice("Achievement draft saved. No missing answers were invented.");
    } catch (error) {
      setFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This draft changed in another tab. Reload before saving."
          : requestErrorMessage(
              error,
              "We couldn’t save this achievement draft.",
            ),
      );
    } finally {
      setLoading(false);
    }
  }

  function requestConversion(value: Achievement) {
    const input: AchievementInput = {
      answers: value.answers,
      employerId: value.employerId,
      metric: value.metric,
      projectId: value.projectId,
      title: value.title,
    };
    const nextErrors = validateAchievementConversion(input);
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors);
      setEditing(value);
      setMode("guided");
      setFailure(
        "Complete the required factual prompts before converting this draft to evidence.",
      );
      queueMicrotask(() => errorRef.current?.focus());
      return;
    }
    setPendingConvert(value);
  }

  async function convert() {
    if (!pendingConvert) return;
    setLoading(true);
    setFailure(undefined);
    try {
      const saved = await convertAchievement(pendingConvert);
      setPage((current) =>
        current
          ? {
              ...current,
              data: current.data.map((item) =>
                item.id === saved.id ? saved : item,
              ),
            }
          : current,
      );
      setPendingConvert(undefined);
      setNotice(
        "Achievement converted to evidence. Review the server-authoritative state and eligibility in Evidence Vault.",
      );
    } catch (error) {
      setFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This achievement changed or was already converted. Reload its current state."
          : requestErrorMessage(error, "We couldn’t convert this achievement."),
      );
      setPendingConvert(undefined);
    } finally {
      setLoading(false);
    }
  }

  async function remove() {
    if (!pendingDelete) return;
    setLoading(true);
    setFailure(undefined);
    try {
      await deleteAchievement(pendingDelete);
      setPage((current) =>
        current
          ? {
              ...current,
              data: current.data.filter((item) => item.id !== pendingDelete.id),
            }
          : current,
      );
      setPendingDelete(undefined);
      setNotice("Achievement draft deleted.");
    } catch (error) {
      setFailure(
        requestErrorMessage(
          error,
          "We couldn’t delete this achievement draft.",
        ),
      );
    } finally {
      setLoading(false);
    }
  }

  async function saveReminders(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reminders) return;
    const form = new FormData(event.currentTarget);
    const enabled = form.get("enabled") === "on";
    const day = Number(form.get("dayOfMonth"));
    if (enabled && (!Number.isInteger(day) || day < 1 || day > 28)) {
      setFailure("Choose a reminder day from 1 through 28.");
      return;
    }
    setLoading(true);
    setFailure(undefined);
    try {
      setReminders(
        await updateReminderPreferences(reminders, {
          dayOfMonth: enabled ? day : null,
          enabled,
          timezone: String(form.get("timezone") ?? "").trim(),
        }),
      );
      setNotice("Monthly reminder preferences saved.");
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "We couldn’t save reminder preferences."),
      );
    } finally {
      setLoading(false);
    }
  }

  if (!page && !failure)
    return (
      <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
        <LoadingSkeleton />
      </main>
    );
  if (!page)
    return (
      <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
        <ErrorState
          description={failure ?? "Achievement Inbox could not be loaded."}
          onRetry={load}
          title="Achievement Inbox unavailable"
        />
      </main>
    );

  return (
    <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
      <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="eyebrow">Fact-safe capture</p>
          <h1 className="mt-2 text-2xl font-black tracking-[-0.035em] sm:text-3xl">
            Achievement Inbox
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            Capture outcomes while they are fresh. Blank answers stay blank
            until you provide them.
          </p>
        </div>
        <Button
          onClick={() => {
            setEditing("new");
            setMode("quick");
            setErrors({});
          }}
        >
          <Plus aria-hidden="true" className="size-4" /> Capture achievement
        </Button>
      </header>
      {failure && (
        <Alert
          className="mb-5"
          title="Achievement Inbox not changed"
          tone="danger"
        >
          {failure}
          <Button
            className="mt-3"
            onClick={() => void load()}
            variant="secondary"
          >
            <RefreshCcw aria-hidden="true" className="size-4" /> Reload
          </Button>
        </Alert>
      )}
      {notice && (
        <Alert className="mb-5" title="Saved" tone="success">
          {notice}
        </Alert>
      )}

      {editing && (
        <Card
          className="mb-6 p-5 sm:p-6"
          aria-labelledby="achievement-editor-heading"
        >
          <h2
            className="text-lg font-extrabold"
            id="achievement-editor-heading"
          >
            {editing === "new"
              ? "Capture an achievement"
              : "Edit achievement draft"}
          </h2>
          <div className="mt-5">
            <FieldErrorSummary errors={errors} ref={errorRef} />
            <AchievementEditor
              errors={errors}
              experiences={experiences}
              {...(editing === "new" ? {} : { initial: editing })}
              loading={loading}
              mode={mode}
              onCancel={() => setEditing(undefined)}
              onSubmit={(input) => void save(input)}
              projects={projects}
              setMode={setMode}
            />
          </div>
        </Card>
      )}

      {page.data.length === 0 ? (
        <EmptyState
          action={
            <Button onClick={() => setEditing("new")}>
              <Plus aria-hidden="true" className="size-4" /> Capture achievement
            </Button>
          }
          description="Start with a quick note or use guided prompts. You do not need a resume."
          title="No achievement drafts yet"
        />
      ) : (
        <ul className="grid gap-4 md:grid-cols-2">
          {page.data.map((achievement) => (
            <li key={achievement.id}>
              <Card className="h-full p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <Badge
                      tone={
                        achievement.status === "converted"
                          ? "success"
                          : "neutral"
                      }
                    >
                      {achievement.status}
                    </Badge>
                    <h2 className="mt-3 font-extrabold">
                      {achievement.title || "Untitled draft"}
                    </h2>
                  </div>
                  {achievement.status !== "converted" && (
                    <div className="flex gap-1">
                      <Button
                        aria-label={`Edit ${achievement.title || "draft"}`}
                        className="px-3"
                        onClick={() => {
                          setEditing(achievement);
                          setMode("guided");
                          setErrors({});
                        }}
                        variant="ghost"
                      >
                        <Pencil aria-hidden="true" className="size-4" />
                      </Button>
                      <Button
                        aria-label={`Delete ${achievement.title || "draft"}`}
                        className="px-3"
                        onClick={() => setPendingDelete(achievement)}
                        variant="ghost"
                      >
                        <Trash2 aria-hidden="true" className="size-4" />
                      </Button>
                    </div>
                  )}
                </div>
                <dl className="mt-4 space-y-3">
                  {questions.slice(0, 3).map(([key, label]) => (
                    <div key={key}>
                      <dt className="text-xs font-extrabold text-muted">
                        {label}
                      </dt>
                      <dd className="mt-1 text-sm">
                        {achievement.answers[key] || "Not answered"}
                      </dd>
                    </div>
                  ))}
                </dl>
                <div className="mt-5 flex flex-wrap gap-2">
                  {achievement.status !== "converted" && (
                    <Button
                      onClick={() => requestConversion(achievement)}
                      variant="secondary"
                    >
                      <Award aria-hidden="true" className="size-4" /> Convert to
                      evidence
                    </Button>
                  )}
                  {achievement.evidenceId && (
                    <Link
                      className="text-sm font-extrabold text-primary"
                      href={`/evidence/${encodeURIComponent(achievement.evidenceId)}`}
                    >
                      Review evidence
                    </Link>
                  )}
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}

      {reminders && (
        <Card className="mt-6 p-5 sm:p-6">
          <h2 className="text-lg font-extrabold">Monthly capture reminder</h2>
          <p className="mt-1 text-sm text-muted">
            A day from 1 to 28 avoids invalid calendar dates.
          </p>
          <form
            className="mt-4 grid gap-4 sm:grid-cols-[auto_10rem_1fr_auto] sm:items-end"
            onSubmit={(event) => void saveReminders(event)}
          >
            <CheckboxField
              defaultChecked={reminders.enabled}
              id="achievement-reminders-enabled"
              label="Enable reminders"
              name="enabled"
            />
            <TextField
              defaultValue={reminders.dayOfMonth ?? 1}
              id="achievement-reminder-day"
              label="Day of month"
              max={28}
              min={1}
              name="dayOfMonth"
              type="number"
            />
            <TextField
              defaultValue={reminders.timezone}
              id="achievement-reminder-timezone"
              label="IANA timezone"
              maxLength={64}
              name="timezone"
              required
            />
            <Button
              loading={loading}
              loadingLabel="Saving reminder…"
              type="submit"
            >
              Save reminder
            </Button>
          </form>
        </Card>
      )}

      <ConfirmDialog
        confirmLabel="Convert to evidence"
        description="Rezumi will preserve this draft, create evidence atomically, and compute state and eligibility on the server. Review the resulting evidence before using it."
        loading={loading}
        onConfirm={() => void convert()}
        onOpenChange={(open) => {
          if (!open && !loading) setPendingConvert(undefined);
        }}
        open={Boolean(pendingConvert)}
        title="Convert this achievement?"
      />
      <ConfirmDialog
        confirmLabel="Delete draft"
        description="This removes the unconverted draft. Existing evidence is never deleted through this action."
        loading={loading}
        onConfirm={() => void remove()}
        onOpenChange={(open) => {
          if (!open && !loading) setPendingDelete(undefined);
        }}
        open={Boolean(pendingDelete)}
        title="Delete this achievement draft?"
      />
    </main>
  );
}
