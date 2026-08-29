"use client";

import {
  Archive,
  Award,
  CheckCircle2,
  Circle,
  Plus,
  RefreshCcw,
  Settings,
} from "lucide-react";
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
  ConfirmDialog,
  ErrorState,
  LoadingSkeleton,
  Tabs,
  TextField,
  cn,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  ApiRequestError,
  confirmExperience,
  getCareerItems,
  createExperience,
  deleteExperience,
  getCareerProfile,
  getCareerRelationships,
  getExperiences,
  getPersonalFacts,
  getSkills,
  reorderExperiences,
  updateCareerProfile,
  updateExperience,
} from "../api/career-vault-api";
import type {
  CareerProfile,
  CareerProfileUpdate,
  CareerRelationship,
  Experience,
  ExperienceInput,
  PersonalFact,
  CareerItem,
  Skill,
} from "../api/types";
import { CareerDetailsSections } from "../components/career-details-sections";
import { CareerTimeline, ExperienceList } from "../components/experience-views";
import { ExperienceForm } from "../components/experience-form";
import { FieldErrorSummary, TextareaField } from "../components/form-controls";
import {
  validateCareerProfile,
  validateExperience,
  type FieldErrors,
} from "../validation/career-vault-validation";

export function CareerProfileView() {
  const [profile, setProfile] = useState<CareerProfile>();
  const [experiences, setExperiences] = useState<Experience[]>();
  const [careerItems, setCareerItems] = useState<CareerItem[]>();
  const [skills, setSkills] = useState<Skill[]>();
  const [personalFacts, setPersonalFacts] = useState<PersonalFact[]>();
  const [relationships, setRelationships] = useState<CareerRelationship[]>();
  const [editingProfile, setEditingProfile] = useState(false);
  const [editingExperience, setEditingExperience] = useState<
    Experience | "new"
  >();
  const [pendingDelete, setPendingDelete] = useState<Experience>();
  const [profileErrors, setProfileErrors] = useState<FieldErrors>({});
  const [experienceErrors, setExperienceErrors] = useState<FieldErrors>({});
  const [failure, setFailure] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const [saving, setSaving] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const profileErrorRef = useRef<HTMLDivElement>(null);
  const experienceErrorRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    setFailure(undefined);
    const [
      nextProfile,
      nextExperiences,
      nextItems,
      nextSkills,
      nextPersonalFacts,
      nextRelationships,
    ] = await Promise.allSettled([
      getCareerProfile(),
      getExperiences(),
      getCareerItems(),
      getSkills(),
      getPersonalFacts(),
      getCareerRelationships(),
    ]);

    if (nextProfile.status === "rejected") {
      setFailure(
        requestErrorMessage(
          nextProfile.reason,
          "We couldn’t load your career profile.",
        ),
      );
      return;
    }

    setProfile(nextProfile.value);
    setExperiences(
      nextExperiences.status === "fulfilled"
        ? nextExperiences.value
        : undefined,
    );
    setCareerItems(
      nextItems.status === "fulfilled" ? nextItems.value : undefined,
    );
    setSkills(nextSkills.status === "fulfilled" ? nextSkills.value : undefined);
    setPersonalFacts(
      nextPersonalFacts.status === "fulfilled"
        ? nextPersonalFacts.value
        : undefined,
    );
    setRelationships(
      nextRelationships.status === "fulfilled"
        ? nextRelationships.value
        : undefined,
    );

    const partialFailure = [
      nextExperiences,
      nextItems,
      nextSkills,
      nextPersonalFacts,
      nextRelationships,
    ].find((result) => result.status === "rejected");
    if (partialFailure?.status === "rejected") {
      setFailure(
        requestErrorMessage(
          partialFailure.reason,
          "Some career profile data could not be loaded. Reload to try again.",
        ),
      );
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!profile) return;
    const form = new FormData(event.currentTarget);
    const input: CareerProfileUpdate = {
      professionalHeadline: String(
        form.get("professionalHeadline") ?? "",
      ).trim(),
      professionalSummary: String(form.get("professionalSummary") ?? "").trim(),
      workAuthorization: String(form.get("workAuthorization") ?? "").trim(),
    };
    const errors = validateCareerProfile(input);
    setProfileErrors(errors);
    if (Object.keys(errors).length > 0) {
      queueMicrotask(() => profileErrorRef.current?.focus());
      return;
    }
    setSaving(true);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      setProfile(await updateCareerProfile(profile, input));
      setEditingProfile(false);
      setSuccess("Career profile saved. No imported source was changed.");
    } catch (error) {
      setFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "Your career profile changed in another tab. Reload the latest version before saving."
          : requestErrorMessage(error, "We couldn’t save your career profile."),
      );
    } finally {
      setSaving(false);
    }
  }

  async function saveExperience(input: ExperienceInput) {
    const errors = validateExperience(input);
    setExperienceErrors(errors);
    if (Object.keys(errors).length > 0) {
      queueMicrotask(() => experienceErrorRef.current?.focus());
      return;
    }
    setSaving(true);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const saved =
        editingExperience === "new" || !editingExperience
          ? await createExperience(input)
          : await updateExperience(editingExperience, input);
      let relationshipViewRefreshed = true;
      try {
        setExperiences(await getExperiences());
      } catch {
        relationshipViewRefreshed = false;
        setExperiences((current = []) => {
          const present = current.some((item) => item.id === saved.id);
          return present
            ? current.map((item) => (item.id === saved.id ? saved : item))
            : [...current, saved];
        });
      }
      setEditingExperience(undefined);
      setExperienceErrors({});
      setSuccess(
        relationshipViewRefreshed
          ? editingExperience === "new"
            ? "Experience added to your career profile."
            : "Experience saved."
          : "Experience saved. Reload to refresh relationship findings.",
      );
    } catch (error) {
      setFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This experience changed in another tab. Reload before saving."
          : requestErrorMessage(error, "We couldn’t save this experience."),
      );
    } finally {
      setSaving(false);
    }
  }

  async function moveExperience(index: number, direction: -1 | 1) {
    if (!experiences) return;
    const target = index + direction;
    if (target < 0 || target >= experiences.length) return;
    const previous = experiences;
    const next = [...experiences];
    const [moved] = next.splice(index, 1);
    if (!moved) return;
    next.splice(target, 0, moved);
    setExperiences(next);
    setAnnouncement(
      `${moved.displayTitle || moved.officialTitle} moved to position ${target + 1} of ${next.length}.`,
    );
    try {
      setExperiences(await reorderExperiences(next));
    } catch (error) {
      setExperiences(previous);
      setAnnouncement("The order was not saved and has been restored.");
      setFailure(
        requestErrorMessage(
          error,
          "We couldn’t save the experience order. Reload and try again.",
        ),
      );
    }
  }

  async function removeExperience() {
    if (!pendingDelete) return;
    setSaving(true);
    setFailure(undefined);
    try {
      await deleteExperience(pendingDelete);
      setExperiences((current = []) =>
        current.filter((item) => item.id !== pendingDelete.id),
      );
      setPendingDelete(undefined);
      setSuccess(
        "Experience deleted. Linked evidence was not silently deleted.",
      );
    } catch (error) {
      setFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This experience changed or still has protected links. Reload to review the current state."
          : requestErrorMessage(error, "We couldn’t delete this experience."),
      );
    } finally {
      setSaving(false);
    }
  }

  async function confirmCurrentExperience(value: Experience) {
    setSaving(true);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const confirmed = await confirmExperience(value);
      setExperiences((current = []) =>
        current.map((item) => (item.id === confirmed.id ? confirmed : item)),
      );
      setSuccess(
        "Experience confirmed. Its current facts are now eligible for grounded downstream use.",
      );
    } catch (error) {
      setFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This experience changed in another tab. Reload before confirming it."
          : requestErrorMessage(
              error,
              "We couldnâ€™t confirm this experience.",
            ),
      );
    } finally {
      setSaving(false);
    }
  }

  if (
    !profile &&
    !experiences &&
    !careerItems &&
    !skills &&
    !personalFacts &&
    !relationships &&
    !failure
  ) {
    return (
      <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
        <LoadingSkeleton />
      </main>
    );
  }
  if (!profile && failure) {
    return (
      <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
        <ErrorState
          description={failure}
          onRetry={load}
          title="Career profile unavailable"
        />
      </main>
    );
  }
  if (!profile) return null;

  const list = experiences ?? [];
  const skillCount = (skills ?? []).length;
  const factCount = (personalFacts ?? []).length;
  const itemCount = (careerItems ?? []).length;
  const completeness = [
    {
      done: Boolean(profile.professionalHeadline),
      label: "Professional headline",
      onClick: () => setEditingProfile(true),
    },
    {
      done: Boolean(profile.professionalSummary),
      label: "Professional summary",
      onClick: () => setEditingProfile(true),
    },
    {
      done: list.length > 0,
      label: "At least one experience",
      onClick: () => {
        setEditingExperience("new");
        setExperienceErrors({});
      },
    },
    {
      done: skillCount > 0,
      label: "At least one skill",
      href: "#skills-heading",
    },
    {
      done: factCount > 0,
      label: "Contact facts",
      href: "#personal-facts-heading",
    },
  ] as const;
  const completedCount = completeness.filter((item) => item.done).length;
  const listPanel = (
    <div className="py-5">
      <ExperienceList
        experiences={list}
        onDelete={setPendingDelete}
        onEdit={(value) => {
          setEditingExperience(value);
          setExperienceErrors({});
        }}
        onConfirm={(value) => void confirmCurrentExperience(value)}
        onMove={(index, direction) => void moveExperience(index, direction)}
      />
    </div>
  );
  const timelinePanel = (
    <div className="py-5">
      <CareerTimeline experiences={list} />
    </div>
  );

  return (
    <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
      <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="eyebrow">Career source of truth</p>
          <h1 className="mt-2 text-2xl font-black tracking-[-0.035em] sm:text-3xl">
            Career Profile
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            Maintain your career facts independently. Resume imports can propose
            changes, but nothing here is overwritten without your review.
          </p>
        </div>
        <Button
          onClick={() => {
            setEditingExperience("new");
            setExperienceErrors({});
          }}
        >
          <Plus aria-hidden="true" className="size-4" /> Add experience
        </Button>
      </header>

      <section
        aria-labelledby="completeness-heading"
        className="mb-5 overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface"
      >
        <div className="grid gap-6 p-5 sm:p-6 lg:grid-cols-[minmax(0,1fr)_auto]">
          <div>
            <h2
              className="text-sm font-bold text-foreground"
              id="completeness-heading"
            >
              Profile completeness — {completedCount}/{completeness.length}
            </h2>
            <ul className="mt-3 grid gap-2 sm:grid-cols-2">
              {completeness.map((item) => {
                const Icon = item.done ? CheckCircle2 : Circle;
                const content = (
                  <>
                    <Icon
                      aria-hidden="true"
                      className={cn(
                        "size-4 shrink-0",
                        item.done ? "text-success" : "text-muted",
                      )}
                    />
                    <span
                      className={item.done ? "text-foreground" : "text-muted"}
                    >
                      {item.label}
                    </span>
                  </>
                );
                return (
                  <li key={item.label}>
                    {item.done ? (
                      <span className="flex items-center gap-2 text-sm">
                        {content}
                      </span>
                    ) : "href" in item ? (
                      <a
                        className="flex items-center gap-2 text-sm font-semibold text-primary-strong hover:underline"
                        href={item.href}
                      >
                        {content}
                      </a>
                    ) : (
                      <button
                        className="flex items-center gap-2 text-sm font-semibold text-primary-strong hover:underline"
                        onClick={item.onClick}
                        type="button"
                      >
                        {content}
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
            {itemCount > 0 && (
              <p className="mt-3 text-xs text-muted">
                Also on file: {itemCount}{" "}
                {itemCount === 1 ? "career record" : "career records"}{" "}
                (education, projects, and more).
              </p>
            )}
          </div>
          <div className="flex flex-col gap-2 border-t border-line pt-4 text-sm font-semibold sm:min-w-48 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
            <Link
              className="flex items-center gap-2 text-primary-strong hover:underline"
              href="/evidence"
            >
              <Archive aria-hidden="true" className="size-4" /> Open Evidence
              Vault
            </Link>
            <Link
              className="flex items-center gap-2 text-primary-strong hover:underline"
              href="/achievement-inbox"
            >
              <Award aria-hidden="true" className="size-4" /> Achievement Inbox
            </Link>
            <Link
              className="flex items-center gap-2 text-primary-strong hover:underline"
              href="/career-profile/imports"
            >
              <RefreshCcw aria-hidden="true" className="size-4" /> Resume
              Imports
            </Link>
          </div>
        </div>
      </section>

      {failure && (
        <Alert
          className="mb-5"
          title="Some career profile data is unavailable"
          tone="danger"
        >
          {failure}
          <Button
            className="mt-3"
            onClick={() => void load()}
            variant="secondary"
          >
            <RefreshCcw aria-hidden="true" className="size-4" /> Reload latest
          </Button>
        </Alert>
      )}
      {success && (
        <Alert className="mb-5" title="Saved" tone="success">
          {success}
        </Alert>
      )}
      <p aria-live="polite" className="sr-only">
        {announcement}
      </p>

      <div className="grid gap-5">
        <Card className="p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-extrabold">Professional overview</h2>
              <p className="mt-1 text-sm text-muted">
                Only these career-record fields are edited here.
              </p>
            </div>
            <Button
              onClick={() => setEditingProfile((value) => !value)}
              variant="secondary"
            >
              {editingProfile ? "Close editor" : "Edit overview"}
            </Button>
          </div>
          {editingProfile ? (
            <form className="mt-5 space-y-5" onSubmit={saveProfile}>
              <FieldErrorSummary errors={profileErrors} ref={profileErrorRef} />
              <TextField
                defaultValue={profile.professionalHeadline}
                error={profileErrors.professionalHeadline}
                id="professional-headline"
                label="Professional headline"
                maxLength={240}
                name="professionalHeadline"
              />
              <TextareaField
                defaultValue={profile.professionalSummary}
                error={profileErrors.professionalSummary}
                hint="Do not add employers, metrics, technologies, or scope that your evidence does not support."
                id="professional-summary"
                label="Professional summary"
                maxLength={4_000}
                name="professionalSummary"
              />
              <TextareaField
                defaultValue={profile.workAuthorization}
                error={profileErrors.workAuthorization}
                id="work-authorization"
                label="Work authorization"
                maxLength={500}
                name="workAuthorization"
              />
              <div className="flex justify-end">
                <Button
                  loading={saving}
                  loadingLabel="Saving profile…"
                  type="submit"
                >
                  Save overview
                </Button>
              </div>
            </form>
          ) : (
            <div className="mt-5 space-y-4">
              <div>
                <p className="text-xs font-extrabold uppercase tracking-wide text-muted">
                  Headline
                </p>
                <p className="mt-1 text-sm">
                  {profile.professionalHeadline || "Not added"}
                </p>
              </div>
              <div>
                <p className="text-xs font-extrabold uppercase tracking-wide text-muted">
                  Summary
                </p>
                <p className="mt-1 whitespace-pre-wrap text-sm leading-6">
                  {profile.professionalSummary || "Not added"}
                </p>
              </div>
              <div>
                <p className="text-xs font-extrabold uppercase tracking-wide text-muted">
                  Work authorization
                </p>
                <p className="mt-1 text-sm">
                  {profile.workAuthorization || "Not added"}
                </p>
              </div>
            </div>
          )}
        </Card>

        <div className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-card)] border border-line bg-surface-subtle px-4 py-3 text-sm">
          <p className="text-muted">
            <span className="font-bold text-foreground">
              {profile.accountPreferences.displayName}
            </span>{" "}
            · {profile.accountPreferences.targetRole || "No target role"} ·{" "}
            {profile.accountPreferences.preferredLocation || "No location"} ·{" "}
            {profile.accountPreferences.workModel || "No work model"}
          </p>
          <Link
            className="flex items-center gap-1.5 font-semibold text-primary-strong hover:underline"
            href="/settings"
          >
            <Settings aria-hidden="true" className="size-4" /> Edit in Settings
          </Link>
        </div>
      </div>

      {editingExperience && (
        <Card
          className="mt-5 p-5 sm:p-6"
          aria-labelledby="experience-editor-heading"
        >
          <h2 className="text-lg font-extrabold" id="experience-editor-heading">
            {editingExperience === "new" ? "Add experience" : "Edit experience"}
          </h2>
          <p className="mt-1 text-sm leading-6 text-muted">
            Dates use month-and-year precision. Missing days are never invented.
          </p>
          <div className="mt-5">
            <FieldErrorSummary
              errors={experienceErrors}
              ref={experienceErrorRef}
            />
            <ExperienceForm
              errors={experienceErrors}
              experiences={list}
              {...(editingExperience === "new"
                ? {}
                : { initial: editingExperience })}
              loading={saving}
              onCancel={() => setEditingExperience(undefined)}
              onSubmit={(value) => void saveExperience(value)}
              skills={skills ?? []}
            />
          </div>
        </Card>
      )}

      <section aria-labelledby="experience-heading" className="mt-8">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-extrabold" id="experience-heading">
              Employment history
            </h2>
            <p className="mt-1 text-sm text-muted">
              Promotion, concurrent-role, conflict, and neutral gap findings
              come from persisted data.
            </p>
          </div>
          <Badge tone={list.length > 0 ? "success" : "neutral"}>
            {list.length} {list.length === 1 ? "entry" : "entries"}
          </Badge>
        </div>
        <Tabs
          label="Career profile views"
          tabs={[
            { id: "timeline", label: "Timeline", panel: timelinePanel },
            { id: "list", label: "List and reorder", panel: listPanel },
          ]}
        />
      </section>

      <CareerDetailsSections
        experiences={list}
        facts={personalFacts ?? []}
        items={careerItems ?? []}
        onFactsChange={setPersonalFacts}
        onItemsChange={setCareerItems}
        onRelationshipsChange={setRelationships}
        onSkillsChange={setSkills}
        skills={skills ?? []}
        relationships={relationships ?? []}
      />

      <ConfirmDialog
        confirmLabel="Delete experience"
        description="This removes the career-profile entry. Linked evidence is preserved and may become conflicted or ineligible; it is never silently deleted."
        loading={saving}
        onConfirm={() => void removeExperience()}
        onOpenChange={(open) => {
          if (!open && !saving) setPendingDelete(undefined);
        }}
        open={Boolean(pendingDelete)}
        title="Delete this experience?"
      />
    </main>
  );
}
