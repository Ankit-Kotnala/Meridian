"use client";

import { ChevronDown, Pencil, Plus, RefreshCcw, Upload } from "lucide-react";
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
  Button,
  Card,
  ConfirmDialog,
  ErrorState,
  LoadingSkeleton,
  TextField,
  cn,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  ApiRequestError,
  confirmCareerItem,
  confirmExperience,
  confirmPersonalFact,
  confirmSkill,
  createCareerItem,
  createCareerRelationship,
  createExperience,
  createPersonalFact,
  createSkill,
  deleteCareerItem,
  deleteCareerRelationship,
  deleteExperience,
  deletePersonalFact,
  deleteSkill,
  enqueuePersonalFactEnrichment,
  getCareerItems,
  getCareerProfile,
  getCareerRelationships,
  getEvidence,
  getExperiences,
  getPersonalFactEnrichmentJob,
  getPersonalFacts,
  getSkills,
  reorderExperiences,
  updateCareerItem,
  updateCareerProfile,
  updateExperience,
  updatePersonalFact,
  updateSkill,
} from "../api/career-vault-api";
import type {
  CareerItem,
  CareerItemInput,
  CareerProfile,
  CareerProfileUpdate,
  CareerRelationship,
  Experience,
  ExperienceInput,
  PersonalFact,
  PersonalFactInput,
  Skill,
  SkillInput,
} from "../api/types";
import { CareerItemForm } from "../components/career-item-form";
import { EmploymentTable } from "../components/experience-views";
import { ExperienceForm } from "../components/experience-form";
import { FieldErrorSummary, TextareaField } from "../components/form-controls";
import {
  PersonalFactForm,
  factKindLabels,
} from "../components/personal-fact-form";
import { ProfilePanel } from "../components/profile-record-ui";
import {
  CareerItemsTable,
  ContactFactsTable,
} from "../components/profile-record-tables";
import { SkillConstellation } from "../components/skill-constellation";
import { ProfileSideNav } from "../components/profile-side-nav";
import {
  ProfileStatusRail,
  type ProfileGap,
} from "../components/profile-status-rail";
import { SkillForm } from "../components/skill-form";
import {
  validateCareerProfile,
  validateExperience,
  type FieldErrors,
} from "../validation/career-vault-validation";

const primaryAction =
  "inline-flex min-h-10 items-center justify-center gap-2 rounded-[var(--radius-control)] border border-info bg-info px-4 text-sm font-semibold text-white transition-colors hover:border-info-strong hover:bg-info-strong";
const secondaryAction =
  "inline-flex min-h-10 items-center justify-center gap-2 rounded-[var(--radius-control)] border border-line-strong bg-surface px-4 text-sm font-semibold text-foreground transition-colors hover:border-info/40 hover:bg-info-soft";
const panelAction =
  "inline-flex min-h-8 items-center justify-center gap-1.5 rounded-[var(--radius-control)] border border-line-strong bg-surface px-3 text-[0.8125rem] font-semibold text-foreground transition-colors hover:border-info/40 hover:bg-info-soft";

/**
 * The active inline editor. Exactly one record editor is open at a time so the
 * page never presents two competing "save" affordances for the same record.
 */
type Editor =
  | { kind: "experience"; value: Experience | null }
  | { kind: "fact"; value: PersonalFact | null }
  | { kind: "item"; value: CareerItem | null }
  | { kind: "skill"; value: Skill | null };

type PendingDelete =
  | { kind: "experience"; value: Experience }
  | { kind: "fact"; value: PersonalFact }
  | { kind: "item"; value: CareerItem }
  | { kind: "skill"; value: Skill };

const deleteCopy: Record<
  PendingDelete["kind"],
  { confirmLabel: string; description: string; title: string }
> = {
  experience: {
    confirmLabel: "Delete employment",
    description:
      "This removes the career-profile entry. Linked evidence is preserved and may become conflicted or ineligible; it is never silently deleted.",
    title: "Delete this employment record?",
  },
  fact: {
    confirmLabel: "Delete contact fact",
    description:
      "This removes the contact fact from the career record. Existing audit history remains.",
    title: "Delete this contact fact?",
  },
  item: {
    confirmLabel: "Delete record",
    description:
      "This removes the career-profile record. Linked evidence is preserved and may require conflict review.",
    title: "Delete this career record?",
  },
  skill: {
    confirmLabel: "Delete skill",
    description:
      "This removes the skill from the profile. Linked evidence is preserved rather than silently deleted.",
    title: "Delete this skill?",
  },
};

function AddRecordMenu({ onSelect }: { onSelect: (editor: Editor) => void }) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(event: PointerEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setOpen(false);
      triggerRef.current?.focus();
    }
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  const options: { editor: Editor; label: string }[] = [
    { editor: { kind: "experience", value: null }, label: "Employment" },
    { editor: { kind: "item", value: null }, label: "Education or project" },
    { editor: { kind: "fact", value: null }, label: "Contact fact" },
    { editor: { kind: "skill", value: null }, label: "Skill" },
  ];

  return (
    <div className="relative" ref={containerRef}>
      <button
        aria-expanded={open}
        aria-haspopup="menu"
        className={primaryAction}
        onClick={() => setOpen((value) => !value)}
        ref={triggerRef}
        type="button"
      >
        <Plus aria-hidden="true" className="size-4" />
        Add record
        <ChevronDown
          aria-hidden="true"
          className={cn("size-3.5 transition-transform", open && "rotate-180")}
        />
      </button>
      {open && (
        <div
          aria-label="Add a career record"
          className="absolute right-0 top-12 z-30 w-60 overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface p-1 shadow-[var(--shadow-lg)]"
          role="menu"
        >
          {options.map((option) => (
            <button
              className="flex min-h-9 w-full items-center rounded-[var(--radius-control)] px-3 text-left text-[0.8125rem] font-semibold text-foreground transition-colors hover:bg-surface-subtle"
              key={option.label}
              onClick={() => {
                setOpen(false);
                onSelect(option.editor);
              }}
              role="menuitem"
              type="button"
            >
              {option.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function OverviewField({
  children,
  label,
}: {
  children: ReactNode;
  label: string;
}) {
  return (
    <div className="grid gap-1 sm:grid-cols-[10.5rem_minmax(0,1fr)] sm:gap-4">
      <dt className="text-[0.8125rem] font-semibold text-foreground">
        {label}
      </dt>
      <dd className="whitespace-pre-wrap text-[0.8125rem] leading-6 text-muted">
        {children}
      </dd>
    </div>
  );
}

export function CareerProfileView() {
  const [profile, setProfile] = useState<CareerProfile>();
  const [experiences, setExperiences] = useState<Experience[]>();
  const [careerItems, setCareerItems] = useState<CareerItem[]>();
  const [skills, setSkills] = useState<Skill[]>();
  const [personalFacts, setPersonalFacts] = useState<PersonalFact[]>();
  const [relationships, setRelationships] = useState<CareerRelationship[]>();
  const [skillEvidenceCounts, setSkillEvidenceCounts] =
    useState<Record<string, number>>();
  const [editingOverview, setEditingOverview] = useState(false);
  const [editor, setEditor] = useState<Editor>();
  const [pendingDelete, setPendingDelete] = useState<PendingDelete>();
  const [profileErrors, setProfileErrors] = useState<FieldErrors>({});
  const [recordErrors, setRecordErrors] = useState<FieldErrors>({});
  const [failure, setFailure] = useState<string>();
  // Load failures offer a reload; a rejected save does not — the record simply
  // was not changed, and re-reading would discard what the user typed.
  const [failureScope, setFailureScope] = useState<"action" | "load">("load");
  const [success, setSuccess] = useState<string>();
  const [saving, setSaving] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const profileErrorRef = useRef<HTMLDivElement>(null);
  const recordErrorRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<HTMLHeadingElement>(null);

  const load = useCallback(async () => {
    setFailure(undefined);
    setFailureScope("load");
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

  /**
   * Evidence counts are a read-only decoration on the skills table. A failure
   * here leaves the column showing "—" rather than blocking the record.
   */
  const loadSkillEvidence = useCallback(async () => {
    try {
      const page = await getEvidence();
      const counts: Record<string, number> = {};
      for (const item of page.data) {
        for (const usage of item.usage) {
          if (usage.type !== "skill") continue;
          counts[usage.id] = (counts[usage.id] ?? 0) + 1;
        }
      }
      setSkillEvidenceCounts(counts);
    } catch {
      setSkillEvidenceCounts(undefined);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void load());
    queueMicrotask(() => void loadSkillEvidence());
  }, [load, loadSkillEvidence]);

  // Focus follows the editor once it exists in the DOM, rather than being
  // scheduled from the click handler that opened it.
  useEffect(() => {
    if (!editor) return;
    editorRef.current?.scrollIntoView?.({ block: "center" });
    editorRef.current?.focus();
  }, [editor]);

  function reportFailure(message: string) {
    setFailureScope("action");
    setFailure(message);
  }

  function openEditor(next: Editor) {
    setEditor(next);
    setRecordErrors({});
    setEditingOverview(false);
  }

  async function saveOverview(event: FormEvent<HTMLFormElement>) {
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
      setEditingOverview(false);
      setSuccess("Career profile saved. No imported source was changed.");
    } catch (error) {
      reportFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "Your career profile changed in another tab. Reload the latest version before saving."
          : requestErrorMessage(error, "We couldn’t save your career profile."),
      );
    } finally {
      setSaving(false);
    }
  }

  async function saveExperience(input: ExperienceInput) {
    if (editor?.kind !== "experience") return;
    const errors = validateExperience(input);
    setRecordErrors(errors);
    if (Object.keys(errors).length > 0) {
      queueMicrotask(() => recordErrorRef.current?.focus());
      return;
    }
    const existing = editor.value;
    setSaving(true);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const saved = existing
        ? await updateExperience(existing, input)
        : await createExperience(input);
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
      setEditor(undefined);
      setRecordErrors({});
      setSuccess(
        relationshipViewRefreshed
          ? existing
            ? "Employment saved."
            : "Employment added to your career profile."
          : "Employment saved. Reload to refresh relationship findings.",
      );
    } catch (error) {
      reportFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This employment record changed in another tab. Reload before saving."
          : requestErrorMessage(error, "We couldn’t save this employment."),
      );
    } finally {
      setSaving(false);
    }
  }

  async function reorderExperienceTo(from: number, to: number) {
    if (!experiences) return;
    if (from === to || to < 0 || to >= experiences.length) return;
    const previous = experiences;
    const next = [...experiences];
    const [moved] = next.splice(from, 1);
    if (!moved) return;
    next.splice(to, 0, moved);
    setExperiences(next);
    setAnnouncement(
      `${moved.displayTitle || moved.officialTitle} moved to position ${to + 1} of ${next.length}.`,
    );
    try {
      setExperiences(await reorderExperiences(next));
    } catch (error) {
      setExperiences(previous);
      setAnnouncement("The order was not saved and has been restored.");
      reportFailure(
        requestErrorMessage(
          error,
          "We couldn’t save the employment order. Reload and try again.",
        ),
      );
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
        "Employment confirmed. Its current facts are now eligible for grounded downstream use.",
      );
    } catch (error) {
      reportFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This employment record changed in another tab. Reload before confirming it."
          : requestErrorMessage(error, "We couldn’t confirm this employment."),
      );
    } finally {
      setSaving(false);
    }
  }

  async function saveFact(input: PersonalFactInput) {
    if (editor?.kind !== "fact") return;
    if (!input.value) {
      reportFailure("Enter a value before saving this contact fact.");
      return;
    }
    const existing = editor.value;
    setSaving(true);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const saved = existing
        ? await updatePersonalFact(existing, {
            isPrimary: input.isPrimary,
            label: input.label,
            value: input.value,
          })
        : await createPersonalFact(input);
      setPersonalFacts((current = []) =>
        current.some((fact) => fact.id === saved.id)
          ? current.map((fact) => (fact.id === saved.id ? saved : fact))
          : [...current, saved],
      );
      setEditor(undefined);
      setSuccess(
        "Contact fact saved. Confirm it separately before downstream use.",
      );
    } catch (error) {
      reportFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This contact fact changed in another tab. Reload before saving."
          : requestErrorMessage(error, "We couldn’t save this contact fact."),
      );
    } finally {
      setSaving(false);
    }
  }

  async function setFactPrimary(fact: PersonalFact, primary: boolean) {
    setSaving(true);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const saved = await updatePersonalFact(fact, {
        isPrimary: primary,
        label: fact.label,
        value: fact.value,
      });
      // The server owns "only one primary per kind", so re-read rather than
      // guessing which sibling was demoted.
      try {
        setPersonalFacts(await getPersonalFacts());
      } catch {
        setPersonalFacts((current = []) =>
          current.map((item) => (item.id === saved.id ? saved : item)),
        );
      }
      setSuccess(
        primary
          ? `This ${factKindLabels[fact.kind].toLowerCase()} is now the primary value.`
          : `This ${factKindLabels[fact.kind].toLowerCase()} is no longer the primary value.`,
      );
    } catch (error) {
      reportFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This contact fact changed in another tab. Reload before changing it."
          : requestErrorMessage(error, "We couldn’t update this contact fact."),
      );
    } finally {
      setSaving(false);
    }
  }

  async function confirmFact(fact: PersonalFact) {
    setSaving(true);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const confirmed = await confirmPersonalFact(fact);
      setPersonalFacts((current = []) =>
        current.map((item) => (item.id === confirmed.id ? confirmed : item)),
      );
      setSuccess("Contact fact confirmed.");
    } catch (error) {
      reportFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This contact fact changed in another tab. Reload before confirming it."
          : requestErrorMessage(
              error,
              "We couldn’t confirm this contact fact.",
            ),
      );
    } finally {
      setSaving(false);
    }
  }

  async function enrichFact(fact: PersonalFact) {
    setSaving(true);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      let job = await enqueuePersonalFactEnrichment(fact);
      let pollCount = 0;
      const maxPolls = 20;
      while (job.status === "queued" || job.status === "running") {
        if (pollCount >= maxPolls) {
          setSuccess(
            "This import is taking longer than expected and will keep running in the background. Check back in a bit to see the results.",
          );
          return;
        }
        await new Promise((resolve) =>
          setTimeout(resolve, Math.min(4_000, 750 + pollCount * 250)),
        );
        job = await getPersonalFactEnrichmentJob(fact, job.jobId);
        pollCount += 1;
      }
      if (job.status === "succeeded") {
        const achievements = job.resultAchievementsCreated ?? 0;
        const evidence = job.resultEvidenceCreated ?? 0;
        setSuccess(
          `Imported ${achievements} achievement${achievements === 1 ? "" : "s"} and ${evidence} evidence item${evidence === 1 ? "" : "s"} from your ${job.resultPlatform ?? "linked"} profile. Review them in Achievement Inbox and Evidence Vault.`,
        );
      } else {
        reportFailure(
          job.errorMessage ??
            "We could not import achievements from this link.",
        );
      }
    } catch (error) {
      reportFailure(
        requestErrorMessage(
          error,
          "We could not import achievements from this link.",
        ),
      );
    } finally {
      setSaving(false);
    }
  }

  async function saveItem(input: CareerItemInput) {
    if (editor?.kind !== "item") return;
    const existing = editor.value;
    setSaving(true);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const saved = existing
        ? await updateCareerItem(existing, input)
        : await createCareerItem(input);
      setCareerItems((current = []) =>
        current.some((item) => item.id === saved.id)
          ? current.map((item) => (item.id === saved.id ? saved : item))
          : [...current, saved],
      );
      setEditor(undefined);
      setRecordErrors({});
      setSuccess("Career record saved.");
    } catch (error) {
      reportFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This career record changed in another tab. Reload before saving."
          : requestErrorMessage(error, "We couldn’t save this career record."),
      );
    } finally {
      setSaving(false);
    }
  }

  async function confirmItem(item: CareerItem) {
    setSaving(true);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const confirmed = await confirmCareerItem(item);
      setCareerItems((current = []) =>
        current.map((candidate) =>
          candidate.id === confirmed.id ? confirmed : candidate,
        ),
      );
      setSuccess(
        "Career record confirmed. Its current facts are eligible for grounded downstream use.",
      );
    } catch (error) {
      reportFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This career record changed in another tab. Reload before confirming it."
          : requestErrorMessage(
              error,
              "We couldn’t confirm this career record.",
            ),
      );
    } finally {
      setSaving(false);
    }
  }

  async function saveSkill(input: SkillInput) {
    if (editor?.kind !== "skill") return;
    const existing = editor.value;
    setSaving(true);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const saved = existing
        ? await updateSkill(existing, input)
        : await createSkill(input);
      setSkills((current = []) =>
        current.some((skill) => skill.id === saved.id)
          ? current.map((skill) => (skill.id === saved.id ? saved : skill))
          : [...current, saved],
      );
      setEditor(undefined);
      setRecordErrors({});
      setSuccess("Skill saved.");
    } catch (error) {
      reportFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This skill changed in another tab. Reload before saving."
          : requestErrorMessage(error, "We couldn’t save this skill."),
      );
    } finally {
      setSaving(false);
    }
  }

  async function confirmCurrentSkill(skill: Skill) {
    setSaving(true);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const confirmed = await confirmSkill(skill);
      setSkills((current = []) =>
        current.map((candidate) =>
          candidate.id === confirmed.id ? confirmed : candidate,
        ),
      );
      setSuccess(
        "Skill confirmed. Its current value is eligible for grounded downstream use.",
      );
    } catch (error) {
      reportFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This skill changed in another tab. Reload before confirming it."
          : requestErrorMessage(error, "We couldn’t confirm this skill."),
      );
    } finally {
      setSaving(false);
    }
  }

  async function linkProject(project: CareerItem, experienceId: string) {
    if (!experienceId) {
      reportFailure("Choose an experience before linking this project.");
      return;
    }
    setSaving(true);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const relationship = await createCareerRelationship(
        experienceId,
        project.id,
      );
      setRelationships((current = []) => [...current, relationship]);
      setSuccess("Project linked to experience.");
    } catch (error) {
      reportFailure(
        requestErrorMessage(error, "We couldn’t link this project."),
      );
    } finally {
      setSaving(false);
    }
  }

  async function unlinkProject(relationship: CareerRelationship) {
    setSaving(true);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      await deleteCareerRelationship(relationship);
      setRelationships((current = []) =>
        current.filter((item) => item.id !== relationship.id),
      );
      setSuccess("Project relationship removed.");
    } catch (error) {
      reportFailure(
        requestErrorMessage(
          error,
          "We couldn’t remove this project relationship.",
        ),
      );
    } finally {
      setSaving(false);
    }
  }

  async function removePendingRecord() {
    if (!pendingDelete) return;
    setSaving(true);
    setFailure(undefined);
    try {
      if (pendingDelete.kind === "experience") {
        await deleteExperience(pendingDelete.value);
        setExperiences((current = []) =>
          current.filter((item) => item.id !== pendingDelete.value.id),
        );
        setSuccess(
          "Employment deleted. Linked evidence was not silently deleted.",
        );
      } else if (pendingDelete.kind === "fact") {
        await deletePersonalFact(pendingDelete.value);
        setPersonalFacts((current = []) =>
          current.filter((item) => item.id !== pendingDelete.value.id),
        );
        setSuccess("Contact fact deleted.");
      } else if (pendingDelete.kind === "item") {
        await deleteCareerItem(pendingDelete.value);
        setCareerItems((current = []) =>
          current.filter((item) => item.id !== pendingDelete.value.id),
        );
        setSuccess("Career record deleted. Evidence was preserved.");
      } else {
        await deleteSkill(pendingDelete.value);
        setSkills((current = []) =>
          current.filter((item) => item.id !== pendingDelete.value.id),
        );
        setSuccess("Skill deleted. Evidence was preserved.");
      }
      setPendingDelete(undefined);
    } catch (error) {
      reportFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This record changed or still has protected links. Reload to review the current state."
          : requestErrorMessage(error, "We couldn’t delete this record."),
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
      <main className="workspace-page" id="main-content">
        <LoadingSkeleton />
      </main>
    );
  }
  if (!profile && failure) {
    return (
      <main className="workspace-page" id="main-content">
        <ErrorState
          description={failure}
          onRetry={load}
          title="Career profile unavailable"
        />
      </main>
    );
  }
  if (!profile) return null;

  const experienceList = experiences ?? [];
  const itemList = careerItems ?? [];
  const skillList = skills ?? [];
  const factList = personalFacts ?? [];
  const preferences = profile.accountPreferences;

  const sectionsComplete = [
    Boolean(profile.professionalHeadline && profile.professionalSummary),
    experienceList.length > 0,
    factList.length > 0,
    itemList.length > 0,
    skillList.length > 0,
  ];
  const completedCount = sectionsComplete.filter(Boolean).length;

  const gaps: ProfileGap[] = [
    {
      done: Boolean(profile.professionalHeadline),
      href: null,
      label: "Headline",
      onSelect: () => setEditingOverview(true),
    },
    {
      done: Boolean(profile.professionalSummary),
      href: null,
      label: "Professional summary",
      onSelect: () => setEditingOverview(true),
    },
    {
      done: Boolean(preferences.targetRole),
      href: "/settings",
      label: "Target role",
      onSelect: null,
    },
    {
      done: experienceList.length > 0,
      href: null,
      label: "Employment history",
      onSelect: () => openEditor({ kind: "experience", value: null }),
    },
    {
      done: factList.length > 0,
      href: null,
      label: "Contact details",
      onSelect: () => openEditor({ kind: "fact", value: null }),
    },
    {
      done: skillList.length > 0,
      href: null,
      label: "Skills",
      onSelect: () => openEditor({ kind: "skill", value: null }),
    },
  ]
    .filter((gap) => !gap.done)
    .map(({ href, label, onSelect }) => ({ href, label, onSelect }));

  return (
    <main className="workspace-page" id="main-content">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_17.5rem]">
        <div className="min-w-0">
          <nav aria-label="Breadcrumb">
            <ol className="flex items-center gap-1.5 text-xs font-semibold text-muted">
              <li>
                <Link className="hover:text-foreground" href="/career-profile">
                  Profile
                </Link>
              </li>
              <li aria-hidden="true">/</li>
              <li aria-current="page" className="text-muted-strong">
                Career record
              </li>
            </ol>
          </nav>

          <header className="mt-2 flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <h1 className="text-[1.75rem] font-bold tracking-[-0.03em] text-foreground">
                Career profile
              </h1>
              <p className="mt-1 text-[0.8125rem] text-muted">
                The verified source used across your resumes and applications.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2.5">
              <AddRecordMenu onSelect={openEditor} />
              <Link className={secondaryAction} href="/career-profile/imports">
                <Upload aria-hidden="true" className="size-4" />
                Import resume
              </Link>
            </div>
          </header>

          {failure && (
            <Alert
              className="mt-5"
              title={
                failureScope === "load"
                  ? "Some career profile data is unavailable"
                  : "Career record not changed"
              }
              tone="danger"
            >
              {failure}
              {failureScope === "load" && (
                <Button
                  className="mt-3"
                  onClick={() => void load()}
                  variant="secondary"
                >
                  <RefreshCcw aria-hidden="true" className="size-4" /> Reload
                  latest
                </Button>
              )}
            </Alert>
          )}
          {success && (
            <Alert className="mt-5" title="Saved" tone="success">
              {success}
            </Alert>
          )}
          <p aria-live="polite" className="sr-only">
            {announcement}
          </p>

          <div className="mt-5 grid gap-5 lg:grid-cols-[12.75rem_minmax(0,1fr)] lg:items-start">
            <ProfileSideNav
              completedCount={completedCount}
              totalCount={sectionsComplete.length}
            />

            <div className="min-w-0 space-y-4">
              {editor && (
                <Card
                  aria-labelledby="record-editor-heading"
                  as="section"
                  className="p-5"
                >
                  <h2
                    className="text-base font-bold text-foreground"
                    id="record-editor-heading"
                    ref={editorRef}
                    tabIndex={-1}
                  >
                    {editor.kind === "experience"
                      ? editor.value
                        ? "Edit employment"
                        : "Add employment"
                      : editor.kind === "fact"
                        ? editor.value
                          ? "Edit contact fact"
                          : "Add contact fact"
                        : editor.kind === "item"
                          ? editor.value
                            ? "Edit career record"
                            : "Add career record"
                          : editor.value
                            ? "Edit skill"
                            : "Add skill"}
                  </h2>
                  {editor.kind === "experience" && (
                    <p className="mt-1 text-[0.8125rem] leading-6 text-muted">
                      Dates use month-and-year precision. Missing days are never
                      invented.
                    </p>
                  )}
                  <div className="mt-5">
                    <FieldErrorSummary
                      errors={recordErrors}
                      ref={recordErrorRef}
                    />
                    {editor.kind === "experience" && (
                      <ExperienceForm
                        errors={recordErrors}
                        experiences={experienceList}
                        {...(editor.value ? { initial: editor.value } : {})}
                        loading={saving}
                        onCancel={() => setEditor(undefined)}
                        onSubmit={(value) => void saveExperience(value)}
                        skills={skillList}
                      />
                    )}
                    {editor.kind === "fact" && (
                      <PersonalFactForm
                        {...(editor.value ? { initial: editor.value } : {})}
                        loading={saving}
                        onCancel={() => setEditor(undefined)}
                        onSubmit={(value) => void saveFact(value)}
                      />
                    )}
                    {editor.kind === "item" && (
                      <CareerItemForm
                        errors={recordErrors}
                        {...(editor.value ? { initial: editor.value } : {})}
                        loading={saving}
                        onCancel={() => setEditor(undefined)}
                        onSubmit={(value) => void saveItem(value)}
                      />
                    )}
                    {editor.kind === "skill" && (
                      <SkillForm
                        errors={recordErrors}
                        {...(editor.value ? { initial: editor.value } : {})}
                        loading={saving}
                        onCancel={() => setEditor(undefined)}
                        onSubmit={(value) => void saveSkill(value)}
                      />
                    )}
                  </div>
                </Card>
              )}

              <ProfilePanel
                action={
                  <button
                    className={panelAction}
                    onClick={() => {
                      setEditor(undefined);
                      setEditingOverview((value) => !value);
                    }}
                    type="button"
                  >
                    <Pencil aria-hidden="true" className="size-3.5" />
                    {editingOverview ? "Close editor" : "Edit overview"}
                  </button>
                }
                id="overview"
                title="Overview"
              >
                {editingOverview ? (
                  <form
                    className="space-y-5 p-4 sm:p-5"
                    onSubmit={saveOverview}
                  >
                    <FieldErrorSummary
                      errors={profileErrors}
                      ref={profileErrorRef}
                    />
                    <TextField
                      defaultValue={profile.professionalHeadline}
                      error={profileErrors.professionalHeadline}
                      id="professional-headline"
                      label="Headline"
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
                    <p className="text-xs leading-5 text-muted">
                      Target role, location, and work model are account
                      preferences.{" "}
                      <Link
                        className="font-semibold text-info hover:underline"
                        href="/settings"
                      >
                        Edit them in Settings
                      </Link>
                      .
                    </p>
                    <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                      <Button
                        disabled={saving}
                        onClick={() => setEditingOverview(false)}
                        variant="secondary"
                      >
                        Cancel
                      </Button>
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
                  <dl className="grid gap-x-10 gap-y-3.5 p-4 sm:p-5 md:grid-cols-2">
                    <OverviewField label="Headline">
                      {profile.professionalHeadline || "Not added"}
                    </OverviewField>
                    <OverviewField label="Target role">
                      {preferences.targetRole || "Not set"}
                    </OverviewField>
                    <OverviewField label="Professional summary">
                      {profile.professionalSummary || "Not added"}
                    </OverviewField>
                    <OverviewField label="Location">
                      {preferences.preferredLocation || "Not set"}
                    </OverviewField>
                    <OverviewField label="Work authorization">
                      {profile.workAuthorization || "Not added"}
                    </OverviewField>
                    <OverviewField label="Work model">
                      {preferences.workModel || "Not set"}
                    </OverviewField>
                  </dl>
                )}
              </ProfilePanel>

              <ProfilePanel
                action={
                  <button
                    className={panelAction}
                    onClick={() =>
                      openEditor({ kind: "experience", value: null })
                    }
                    type="button"
                  >
                    <Plus aria-hidden="true" className="size-3.5" />
                    Add employment
                  </button>
                }
                id="employment"
                title="Employment history"
              >
                <EmploymentTable
                  experiences={experienceList}
                  onConfirm={(value) => void confirmCurrentExperience(value)}
                  onDelete={(value) =>
                    setPendingDelete({ kind: "experience", value })
                  }
                  onEdit={(value) => openEditor({ kind: "experience", value })}
                  onReorder={(from, to) => void reorderExperienceTo(from, to)}
                />
              </ProfilePanel>

              <ProfilePanel
                action={
                  <button
                    className={panelAction}
                    onClick={() => openEditor({ kind: "fact", value: null })}
                    type="button"
                  >
                    <Plus aria-hidden="true" className="size-3.5" />
                    Add contact fact
                  </button>
                }
                id="contact"
                title="Contact facts"
              >
                <ContactFactsTable
                  facts={factList}
                  onConfirm={(fact) => void confirmFact(fact)}
                  onDelete={(value) =>
                    setPendingDelete({ kind: "fact", value })
                  }
                  onEdit={(value) => openEditor({ kind: "fact", value })}
                  onEnrich={(fact) => void enrichFact(fact)}
                  onSetPrimary={(fact, primary) =>
                    void setFactPrimary(fact, primary)
                  }
                  saving={saving}
                />
              </ProfilePanel>

              <ProfilePanel
                action={
                  <button
                    className={panelAction}
                    onClick={() => openEditor({ kind: "item", value: null })}
                    type="button"
                  >
                    <Plus aria-hidden="true" className="size-3.5" />
                    Add career record
                  </button>
                }
                id="education"
                title="Education & projects"
              >
                <CareerItemsTable
                  experiences={experienceList}
                  items={itemList}
                  onConfirm={(item) => void confirmItem(item)}
                  onDelete={(value) =>
                    setPendingDelete({ kind: "item", value })
                  }
                  onEdit={(value) => openEditor({ kind: "item", value })}
                  onLinkProject={(item, experienceId) =>
                    void linkProject(item, experienceId)
                  }
                  onUnlinkProject={(relationship) =>
                    void unlinkProject(relationship)
                  }
                  relationships={relationships ?? []}
                  saving={saving}
                />
              </ProfilePanel>

              <ProfilePanel
                action={
                  <button
                    className={panelAction}
                    onClick={() => openEditor({ kind: "skill", value: null })}
                    type="button"
                  >
                    <Plus aria-hidden="true" className="size-3.5" />
                    Add skill
                  </button>
                }
                allowOverflow
                id="skills"
                title="Skills"
              >
                <SkillConstellation
                  evidenceCounts={skillEvidenceCounts}
                  onConfirm={(skill) => void confirmCurrentSkill(skill)}
                  onDelete={(value) =>
                    setPendingDelete({ kind: "skill", value })
                  }
                  onEdit={(value) => openEditor({ kind: "skill", value })}
                  skills={skillList}
                />
              </ProfilePanel>
            </div>
          </div>
        </div>

        <ProfileStatusRail
          completedCount={completedCount}
          gaps={gaps}
          totalCount={sectionsComplete.length}
          updatedAt={profile.updatedAt}
        />
      </div>

      <ConfirmDialog
        confirmLabel={
          pendingDelete ? deleteCopy[pendingDelete.kind].confirmLabel : "Delete"
        }
        description={
          pendingDelete ? deleteCopy[pendingDelete.kind].description : ""
        }
        loading={saving}
        onConfirm={() => void removePendingRecord()}
        onOpenChange={(open) => {
          if (!open && !saving) setPendingDelete(undefined);
        }}
        open={Boolean(pendingDelete)}
        title={
          pendingDelete
            ? deleteCopy[pendingDelete.kind].title
            : "Delete this record?"
        }
      />
    </main>
  );
}
