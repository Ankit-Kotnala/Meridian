"use client";

import { ArrowLeft, RefreshCcw, Save, Trash2 } from "lucide-react";
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
  ErrorState,
  Input,
  LoadingSkeleton,
  Select,
  buttonStyles,
} from "@careeros/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  ApiRequestError,
  deleteStory,
  getStory,
  updateStory,
} from "../api/interview-prep-api";
import type { StarStory, StoryField, StoryStatus } from "../api/types";
import { useIntentActivity } from "../state/use-intent-activity";

const storyStatuses: readonly StoryStatus[] = ["draft", "ready", "archived"];
const storyFields: ReadonlyArray<{ label: string; value: StoryField }> = [
  { label: "Situation", value: "situation" },
  { label: "Task", value: "task" },
  { label: "Action", value: "action" },
  { label: "Result", value: "result" },
  { label: "Personal contribution", value: "personal_contribution" },
  { label: "Metric explanation", value: "metric_explanation" },
];

function humanize(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function storyTone(status: StoryStatus) {
  if (status === "ready") return "success" as const;
  if (status === "archived") return "neutral" as const;
  return "warning" as const;
}

export function StarStoryDetailView({ storyId }: { storyId: string }) {
  const router = useRouter();
  const [story, setStory] = useState<StarStory>();
  const [failure, setFailure] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const {
    begin: beginIntentActivity,
    end: endIntentActivity,
    isActive: isIntentActive,
  } = useIntentActivity();
  const [deleteOpen, setDeleteOpen] = useState(false);
  const requestEpoch = useRef(0);
  const controller = useRef<AbortController | null>(null);

  const load = useCallback(
    async (message?: string) => {
      controller.current?.abort();
      const nextController = new AbortController();
      controller.current = nextController;
      const epoch = ++requestEpoch.current;
      setFailure(undefined);
      try {
        const current = await getStory(storyId, nextController.signal);
        if (epoch !== requestEpoch.current || nextController.signal.aborted)
          return;
        setStory(current);
        if (message) setFailure(message);
      } catch (error) {
        if (epoch !== requestEpoch.current || nextController.signal.aborted)
          return;
        setFailure(
          requestErrorMessage(error, "The STAR story could not be loaded."),
        );
      }
    },
    [storyId],
  );

  useEffect(() => {
    queueMicrotask(() => void load());
    return () => {
      controller.current?.abort();
      requestEpoch.current += 1;
    };
  }, [load]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!story) return;
    const form = new FormData(event.currentTarget);
    const claimSelections = story.claimPins.map((claim) => ({
      claimId: claim.sourceClaimId,
      fieldNames: form.getAll(`claim-${claim.sourceClaimId}`) as StoryField[],
    }));
    if (
      claimSelections.some((selection) => selection.fieldNames.length === 0)
    ) {
      setFailure("Each pinned claim must support at least one story field.");
      return;
    }
    const activity = beginIntentActivity("save");
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const updated = await updateStory(story, {
        action: String(form.get("action") ?? "").trim(),
        claimSelections,
        confidence: Number(form.get("confidence")),
        followUpQuestions: String(form.get("followUpQuestions") ?? "")
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean),
        metricExplanation:
          String(form.get("metricExplanation") ?? "").trim() || null,
        personalContribution: String(
          form.get("personalContribution") ?? "",
        ).trim(),
        result: String(form.get("result") ?? "").trim(),
        situation: String(form.get("situation") ?? "").trim(),
        status: String(form.get("status")) as StoryStatus,
        task: String(form.get("task") ?? "").trim(),
        title: String(form.get("title") ?? "").trim(),
      });
      setStory(updated);
      setSuccess("Story saved with refreshed exact provenance pins.");
    } catch (error) {
      const stale =
        error instanceof ApiRequestError &&
        (error.failure.status === 409 || error.failure.status === 412);
      if (stale) {
        await load(
          "This story changed in another session. The authoritative version was reloaded; review it before saving again.",
        );
      } else {
        setFailure(requestErrorMessage(error, "The story could not be saved."));
      }
    } finally {
      endIntentActivity(activity);
    }
  }

  async function remove() {
    if (!story) return;
    const activity = beginIntentActivity("delete");
    setFailure(undefined);
    try {
      await deleteStory(story);
      router.replace("/interview-prep");
      router.refresh();
    } catch (error) {
      const stale =
        error instanceof ApiRequestError &&
        (error.failure.status === 409 || error.failure.status === 412);
      setDeleteOpen(false);
      if (stale) {
        await load(
          "This story changed in another session. The authoritative version was reloaded and was not deleted.",
        );
      } else {
        setFailure(
          requestErrorMessage(error, "The story could not be deleted."),
        );
      }
    } finally {
      endIntentActivity(activity);
    }
  }

  if (!story && failure) {
    return (
      <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
        <ErrorState
          description={failure}
          onRetry={() => void load()}
          title="STAR story unavailable"
        />
      </main>
    );
  }

  if (!story) {
    return (
      <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
        <LoadingSkeleton />
      </main>
    );
  }

  return (
    <main
      className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6 lg:p-8"
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
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={storyTone(story.status)}>{humanize(story.status)}</Badge>
          <Badge tone="neutral">Confidence {story.confidence} of 5</Badge>
          <Badge tone="primary">{humanize(story.origin)}</Badge>
          <Badge
            tone={
              story.groundingStatus === "current"
                ? "success"
                : story.groundingStatus === "needs_review"
                  ? "warning"
                  : "neutral"
            }
          >
            {story.groundingStatus === "current"
              ? "Evidence current"
              : humanize(story.groundingStatus)}
          </Badge>
        </div>
        <h1 className="mt-3 text-2xl font-black text-foreground">
          {story.title}
        </h1>
        <p className="mt-2 text-sm text-muted">
          Version {story.version}. Every factual link below is pinned to an
          exact claim and evidence revision hash.
        </p>
      </header>

      {story.groundingStatus !== "current" && (
        <Alert title="Grounding review required" tone="warning">
          {story.groundingWarning ??
            "Current evidence eligibility could not be confirmed. Review and re-ground the story before using it."}
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
            Reload
          </Button>
        </Alert>
      )}
      {success && (
        <Alert title="Story updated" tone="success">
          {success}
        </Alert>
      )}

      <form
        className="space-y-5 rounded-xl border border-line bg-white p-4 shadow-sm sm:p-5"
        key={story.version}
        onSubmit={submit}
      >
        <h2 className="text-lg font-black text-foreground">
          Structured STAR story
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <StoryInput
            defaultValue={story.title}
            id="story-detail-title"
            label="Story title"
            name="title"
            required
          />
          <label className="space-y-2 text-sm font-bold text-foreground">
            Confidence
            <Select defaultValue={String(story.confidence)} name="confidence">
              {[1, 2, 3, 4, 5].map((value) => (
                <option key={value} value={value}>
                  {value} of 5
                </option>
              ))}
            </Select>
          </label>
          <label className="space-y-2 text-sm font-bold text-foreground">
            Status
            <Select defaultValue={story.status} name="status">
              {storyStatuses.map((status) => (
                <option key={status} value={status}>
                  {humanize(status)}
                </option>
              ))}
            </Select>
          </label>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          {[
            ["Situation", "situation", story.situation, 2000],
            ["Task", "task", story.task, 2000],
            ["Action", "action", story.action, 3000],
            ["Result", "result", story.result, 2000],
            [
              "Personal contribution",
              "personalContribution",
              story.personalContribution,
              2000,
            ],
            [
              "Metric explanation (required for any number)",
              "metricExplanation",
              story.metricExplanation ?? "",
              2000,
            ],
          ].map(([label, name, defaultValue, maxLength]) => (
            <StoryTextarea
              defaultValue={String(defaultValue)}
              id={`story-detail-${name}`}
              key={String(name)}
              label={String(label)}
              maxLength={Number(maxLength)}
              name={String(name)}
              required={name !== "metricExplanation"}
            />
          ))}
        </div>
        <StoryTextarea
          defaultValue={story.followUpQuestions.join("\n")}
          id="story-detail-follow-up"
          label="Likely follow-up questions (one per line)"
          maxLength={6000}
          name="followUpQuestions"
        />

        <fieldset className="space-y-4 rounded-xl border border-line p-4">
          <legend className="px-1 text-sm font-black text-foreground">
            Claim-to-story field mapping
          </legend>
          {story.claimPins.map((claim) => (
            <div className="space-y-3" key={claim.sourceClaimId}>
              <p className="text-sm font-semibold leading-6 text-foreground">
                {claim.claimText}
              </p>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {storyFields.map((field) => (
                  <CheckboxField
                    aria-label={`Map ${field.label} to claim: ${claim.claimText}`}
                    defaultChecked={claim.fieldNames.includes(field.value)}
                    id={`claim-${claim.sourceClaimId}-${field.value}`}
                    key={field.value}
                    label={`${field.label} support`}
                    name={`claim-${claim.sourceClaimId}`}
                    value={field.value}
                  />
                ))}
              </div>
            </div>
          ))}
        </fieldset>

        <Button disabled={isIntentActive("save")} type="submit">
          <Save aria-hidden="true" className="size-4" />
          {isIntentActive("save") ? "Saving…" : "Save story"}
        </Button>
      </form>

      <section aria-labelledby="story-provenance" className="space-y-4">
        <div>
          <h2
            className="text-lg font-black text-foreground"
            id="story-provenance"
          >
            Machine-checkable provenance
          </h2>
          <p className="mt-1 text-sm text-muted">
            Numbers are permitted only when the pinned eligible evidence
            supports them.
          </p>
        </div>
        {story.claimPins.map((claim) => (
          <article
            className="rounded-xl border border-line bg-white p-4 shadow-sm"
            key={claim.sourceClaimId}
          >
            <div className="flex flex-wrap gap-2">
              <Badge tone={claim.strong ? "warning" : "neutral"}>
                {claim.strong ? "Strong claim" : "Claim"}
              </Badge>
              <Badge tone="primary">
                {claim.evidencePins.length} exact evidence{" "}
                {claim.evidencePins.length === 1 ? "pin" : "pins"}
              </Badge>
            </div>
            <p className="mt-3 text-sm font-semibold leading-6 text-foreground">
              {claim.claimText}
            </p>
            <dl className="mt-3 space-y-2 text-xs text-muted">
              <div>
                <dt className="font-bold">Claim SHA-256</dt>
                <dd>
                  <code className="break-all">{claim.claimSha256}</code>
                </dd>
              </div>
              <div>
                <dt className="font-bold">Source claim ID</dt>
                <dd>
                  <code className="break-all">{claim.sourceClaimId}</code>
                </dd>
              </div>
            </dl>
            <ul className="mt-4 grid gap-3 lg:grid-cols-2">
              {claim.evidencePins.map((pin) => (
                <li
                  className="rounded-lg border border-line bg-slate-50 p-3"
                  key={pin.evidenceRevisionId}
                >
                  <div className="flex flex-wrap gap-2">
                    <Badge tone="success">{humanize(pin.strength)}</Badge>
                    <span className="text-xs font-bold text-muted">
                      Revision {pin.revisionNumber}
                    </span>
                    {pin.hasNumericClaim && (
                      <Badge tone="warning">Contains number</Badge>
                    )}
                  </div>
                  <p className="mt-2 text-sm leading-6 text-foreground">
                    {pin.statement}
                  </p>
                  <p className="mt-2 text-xs text-muted">
                    SHA-256:{" "}
                    <code className="break-all">{pin.statementSha256}</code>
                  </p>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </section>

      <section className="rounded-xl border border-red-200 bg-white p-4 shadow-sm sm:p-5">
        <h2 className="text-lg font-black text-foreground">Delete story</h2>
        <p className="mt-2 text-sm leading-6 text-muted">
          Deleting removes this story from the defense map. It does not alter
          source claims or evidence.
        </p>
        <Button
          className="mt-4"
          onClick={() => setDeleteOpen(true)}
          variant="danger"
        >
          <Trash2 aria-hidden="true" className="size-4" />
          Delete story
        </Button>
      </section>

      <ConfirmDialog
        confirmLabel="Delete story"
        description="This removes the STAR story and its local provenance links. Source Career Record evidence is unchanged."
        loading={isIntentActive("delete")}
        onConfirm={() => void remove()}
        onOpenChange={setDeleteOpen}
        open={deleteOpen}
        title="Delete this STAR story?"
      />
    </main>
  );
}

function StoryInput({
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

function StoryTextarea({
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
