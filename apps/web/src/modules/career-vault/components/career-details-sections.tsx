"use client";

import { Pencil, Plus, Trash2 } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  CheckboxField,
  ConfirmDialog,
  EmptyState,
  FieldLabel,
  Select,
  TextField,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  ApiRequestError,
  confirmCareerItem,
  confirmPersonalFact,
  confirmSkill,
  createCareerItem,
  createCareerRelationship,
  createPersonalFact,
  createSkill,
  deleteCareerItem,
  deleteCareerRelationship,
  deletePersonalFact,
  deleteSkill,
  updateCareerItem,
  updatePersonalFact,
  updateSkill,
} from "../api/career-vault-api";
import type {
  CareerItem,
  CareerItemInput,
  CareerRelationship,
  Experience,
  PersonalFact,
  PersonalFactInput,
  Skill,
  SkillInput,
} from "../api/types";
import {
  type FieldErrors,
  validateCareerItem,
  validateSkill,
} from "../validation/career-vault-validation";
import { CareerItemForm } from "./career-item-form";
import { ProvenanceList } from "./evidence-semantics";
import { FieldErrorSummary } from "./form-controls";
import { SkillForm } from "./skill-form";

const kindLabels: Record<CareerItem["kind"], string> = {
  award: "Award",
  credential: "Credential",
  education: "Education",
  language: "Language",
  portfolio_link: "Portfolio link",
  project: "Project",
  publication: "Publication",
  volunteering: "Volunteering",
};

const factKindLabels: Record<PersonalFact["kind"], string> = {
  email: "Email",
  link: "Link",
  location: "Location",
  name: "Name",
  phone: "Phone",
};

export function CareerDetailsSections({
  experiences,
  facts,
  items,
  onFactsChange,
  onItemsChange,
  onRelationshipsChange,
  onSkillsChange,
  skills,
  relationships,
}: {
  experiences: Experience[];
  facts: PersonalFact[];
  items: CareerItem[];
  onFactsChange: (facts: PersonalFact[]) => void;
  onItemsChange: (items: CareerItem[]) => void;
  onRelationshipsChange: (relationships: CareerRelationship[]) => void;
  onSkillsChange: (skills: Skill[]) => void;
  skills: Skill[];
  relationships: CareerRelationship[];
}) {
  const [editingItem, setEditingItem] = useState<CareerItem | "new">();
  const [editingFact, setEditingFact] = useState<PersonalFact | "new">();
  const [editingSkill, setEditingSkill] = useState<Skill | "new">();
  const [deleteItem, setDeleteItem] = useState<CareerItem>();
  const [deleteFact, setDeleteFact] = useState<PersonalFact>();
  const [deleteSkillValue, setDeleteSkillValue] = useState<Skill>();
  const [errors, setErrors] = useState<FieldErrors>({});
  const [failure, setFailure] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [saving, setSaving] = useState(false);
  const [selectedExperienceByProject, setSelectedExperienceByProject] =
    useState<Record<string, string>>({});
  const errorRef = useRef<HTMLDivElement>(null);

  async function saveFact(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const value = String(form.get("value") ?? "").trim();
    if (!value) {
      setFailure("Enter a value before saving this contact fact.");
      return;
    }
    const input: PersonalFactInput = {
      isPrimary: form.get("isPrimary") === "on",
      kind:
        editingFact !== undefined && editingFact !== "new"
          ? editingFact.kind
          : (String(form.get("kind")) as PersonalFact["kind"]),
      label: String(form.get("label") ?? "").trim() || null,
      value,
    };
    setSaving(true);
    setFailure(undefined);
    setNotice(undefined);
    try {
      const saved =
        editingFact === "new" || !editingFact
          ? await createPersonalFact(input)
          : await updatePersonalFact(editingFact, {
              isPrimary: input.isPrimary,
              label: input.label,
              value: input.value,
            });
      onFactsChange(
        facts.some((fact) => fact.id === saved.id)
          ? facts.map((fact) => (fact.id === saved.id ? saved : fact))
          : [...facts, saved],
      );
      setEditingFact(undefined);
      setNotice(
        "Contact fact saved. Confirm it separately before downstream use.",
      );
    } catch (error) {
      setFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This contact fact changed in another tab. Reload before saving."
          : requestErrorMessage(error, "We couldnâ€™t save this contact fact."),
      );
    } finally {
      setSaving(false);
    }
  }

  async function confirmFact(fact: PersonalFact) {
    setSaving(true);
    setFailure(undefined);
    setNotice(undefined);
    try {
      const confirmed = await confirmPersonalFact(fact);
      onFactsChange(
        facts.map((candidate) =>
          candidate.id === confirmed.id ? confirmed : candidate,
        ),
      );
      setNotice("Contact fact confirmed.");
    } catch (error) {
      setFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This contact fact changed in another tab. Reload before confirming it."
          : requestErrorMessage(
              error,
              "We couldnâ€™t confirm this contact fact.",
            ),
      );
    } finally {
      setSaving(false);
    }
  }

  async function removeFact() {
    if (!deleteFact) return;
    setSaving(true);
    setFailure(undefined);
    try {
      await deletePersonalFact(deleteFact);
      onFactsChange(facts.filter((fact) => fact.id !== deleteFact.id));
      setDeleteFact(undefined);
      setNotice("Contact fact deleted.");
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "We couldnâ€™t delete this contact fact."),
      );
    } finally {
      setSaving(false);
    }
  }

  async function linkProject(project: CareerItem) {
    const experienceId = selectedExperienceByProject[project.id];
    if (!experienceId) {
      setFailure("Choose an experience before linking this project.");
      return;
    }
    setSaving(true);
    setFailure(undefined);
    setNotice(undefined);
    try {
      const relationship = await createCareerRelationship(
        experienceId,
        project.id,
      );
      onRelationshipsChange([...relationships, relationship]);
      setNotice("Project linked to experience.");
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "We couldnâ€™t link this project."),
      );
    } finally {
      setSaving(false);
    }
  }

  async function unlinkProject(relationship: CareerRelationship) {
    setSaving(true);
    setFailure(undefined);
    setNotice(undefined);
    try {
      await deleteCareerRelationship(relationship);
      onRelationshipsChange(
        relationships.filter((item) => item.id !== relationship.id),
      );
      setNotice("Project relationship removed.");
    } catch (error) {
      setFailure(
        requestErrorMessage(
          error,
          "We couldnâ€™t remove this project relationship.",
        ),
      );
    } finally {
      setSaving(false);
    }
  }

  async function saveItem(input: CareerItemInput) {
    const nextErrors = validateCareerItem(input);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      queueMicrotask(() => errorRef.current?.focus());
      return;
    }
    setSaving(true);
    setFailure(undefined);
    setNotice(undefined);
    try {
      const saved =
        editingItem === "new" || !editingItem
          ? await createCareerItem(input)
          : await updateCareerItem(editingItem, input);
      onItemsChange(
        items.some((item) => item.id === saved.id)
          ? items.map((item) => (item.id === saved.id ? saved : item))
          : [...items, saved],
      );
      setEditingItem(undefined);
      setErrors({});
      setNotice("Career record saved.");
    } catch (error) {
      setFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This career record changed in another tab. Reload before saving."
          : requestErrorMessage(error, "We couldn’t save this career record."),
      );
    } finally {
      setSaving(false);
    }
  }

  async function saveSkill(input: SkillInput) {
    const nextErrors = validateSkill(input);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      queueMicrotask(() => errorRef.current?.focus());
      return;
    }
    setSaving(true);
    setFailure(undefined);
    setNotice(undefined);
    try {
      const saved =
        editingSkill === "new" || !editingSkill
          ? await createSkill(input)
          : await updateSkill(editingSkill, input);
      onSkillsChange(
        skills.some((skill) => skill.id === saved.id)
          ? skills.map((skill) => (skill.id === saved.id ? saved : skill))
          : [...skills, saved],
      );
      setEditingSkill(undefined);
      setErrors({});
      setNotice("Skill saved.");
    } catch (error) {
      setFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This skill changed in another tab. Reload before saving."
          : requestErrorMessage(error, "We couldn’t save this skill."),
      );
    } finally {
      setSaving(false);
    }
  }

  async function confirmItem(item: CareerItem) {
    setSaving(true);
    setFailure(undefined);
    setNotice(undefined);
    try {
      const confirmed = await confirmCareerItem(item);
      onItemsChange(
        items.map((candidate) =>
          candidate.id === confirmed.id ? confirmed : candidate,
        ),
      );
      setNotice(
        "Career record confirmed. Its current facts are eligible for grounded downstream use.",
      );
    } catch (error) {
      setFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This career record changed in another tab. Reload before confirming it."
          : requestErrorMessage(
              error,
              "We couldnâ€™t confirm this career record.",
            ),
      );
    } finally {
      setSaving(false);
    }
  }

  async function confirmCurrentSkill(skill: Skill) {
    setSaving(true);
    setFailure(undefined);
    setNotice(undefined);
    try {
      const confirmed = await confirmSkill(skill);
      onSkillsChange(
        skills.map((candidate) =>
          candidate.id === confirmed.id ? confirmed : candidate,
        ),
      );
      setNotice(
        "Skill confirmed. Its current value is eligible for grounded downstream use.",
      );
    } catch (error) {
      setFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "This skill changed in another tab. Reload before confirming it."
          : requestErrorMessage(error, "We couldnâ€™t confirm this skill."),
      );
    } finally {
      setSaving(false);
    }
  }

  async function removeItem() {
    if (!deleteItem) return;
    setSaving(true);
    setFailure(undefined);
    try {
      await deleteCareerItem(deleteItem);
      onItemsChange(items.filter((item) => item.id !== deleteItem.id));
      setDeleteItem(undefined);
      setNotice("Career record deleted. Evidence was preserved.");
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "We couldn’t delete this career record."),
      );
    } finally {
      setSaving(false);
    }
  }

  async function removeSkill() {
    if (!deleteSkillValue) return;
    setSaving(true);
    setFailure(undefined);
    try {
      await deleteSkill(deleteSkillValue);
      onSkillsChange(
        skills.filter((skill) => skill.id !== deleteSkillValue.id),
      );
      setDeleteSkillValue(undefined);
      setNotice("Skill deleted. Evidence was preserved.");
    } catch (error) {
      setFailure(requestErrorMessage(error, "We couldn’t delete this skill."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mt-8 space-y-8">
      {failure && (
        <Alert title="Career record not changed" tone="danger">
          {failure}
        </Alert>
      )}
      {notice && (
        <Alert title="Saved" tone="success">
          {notice}
        </Alert>
      )}

      <section aria-labelledby="personal-facts-heading">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-extrabold" id="personal-facts-heading">
              Contact facts
            </h2>
            <p className="mt-1 text-sm text-muted">
              Names, contact details, locations, and links are stored as typed
              Career Record facts. Saving does not confirm them.
            </p>
          </div>
          <Button
            onClick={() => {
              setEditingFact("new");
              setEditingItem(undefined);
              setEditingSkill(undefined);
            }}
            variant="secondary"
          >
            <Plus aria-hidden="true" className="size-4" /> Add contact fact
          </Button>
        </div>
        {editingFact && (
          <Card className="mb-4 p-5">
            <h3 className="font-extrabold">
              {editingFact === "new" ? "Add contact fact" : "Edit contact fact"}
            </h3>
            <form className="mt-4 space-y-4" onSubmit={saveFact}>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <FieldLabel htmlFor="personal-fact-kind">
                    Fact type
                  </FieldLabel>
                  <Select
                    defaultValue={
                      editingFact === "new" ? "name" : editingFact.kind
                    }
                    disabled={editingFact !== "new"}
                    id="personal-fact-kind"
                    name="kind"
                  >
                    {Object.entries(factKindLabels).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </Select>
                </div>
                <TextField
                  defaultValue={
                    editingFact === "new" ? "" : (editingFact.label ?? "")
                  }
                  id="personal-fact-label"
                  label="Label (optional)"
                  maxLength={80}
                  name="label"
                />
              </div>
              <TextField
                defaultValue={editingFact === "new" ? "" : editingFact.value}
                id="personal-fact-value"
                label="Value"
                maxLength={2_048}
                name="value"
                required
              />
              <CheckboxField
                defaultChecked={editingFact !== "new" && editingFact.isPrimary}
                id="personal-fact-primary"
                label="Use as the primary value for this fact type"
                name="isPrimary"
              />
              <div className="flex justify-end gap-3">
                <Button
                  disabled={saving}
                  onClick={() => setEditingFact(undefined)}
                  variant="secondary"
                >
                  Cancel
                </Button>
                <Button loading={saving} type="submit">
                  Save contact fact
                </Button>
              </div>
            </form>
          </Card>
        )}
        {facts.length === 0 ? (
          <EmptyState
            description="Add only contact information you want in your structured Career Record."
            title="No contact facts yet"
          />
        ) : (
          <ul className="grid gap-3 md:grid-cols-2">
            {facts.map((fact) => (
              <li key={fact.id}>
                <Card className="h-full p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap gap-2">
                        <Badge tone="neutral">
                          {factKindLabels[fact.kind]}
                        </Badge>
                        {fact.isPrimary && (
                          <Badge tone="primary">Primary</Badge>
                        )}
                        <Badge
                          tone={
                            fact.confirmation === "confirmed"
                              ? "success"
                              : "warning"
                          }
                        >
                          {fact.confirmation === "confirmed"
                            ? "Confirmed"
                            : "Needs review"}
                        </Badge>
                      </div>
                      <p className="mt-3 break-words text-sm font-bold">
                        {fact.value}
                      </p>
                      {fact.label && (
                        <p className="mt-1 text-xs text-muted">{fact.label}</p>
                      )}
                    </div>
                    <div className="flex gap-1">
                      <Button
                        aria-label={`Edit ${factKindLabels[fact.kind]} fact`}
                        className="px-3"
                        onClick={() => setEditingFact(fact)}
                        variant="ghost"
                      >
                        <Pencil aria-hidden="true" className="size-4" />
                      </Button>
                      <Button
                        aria-label={`Delete ${factKindLabels[fact.kind]} fact`}
                        className="px-3"
                        onClick={() => setDeleteFact(fact)}
                        variant="ghost"
                      >
                        <Trash2 aria-hidden="true" className="size-4" />
                      </Button>
                    </div>
                  </div>
                  {fact.confirmation !== "confirmed" && (
                    <Button
                      className="mt-4"
                      onClick={() => void confirmFact(fact)}
                    >
                      Confirm current value
                    </Button>
                  )}
                  {fact.provenance.length > 0 && (
                    <details className="mt-4 rounded-xl border border-line p-3">
                      <summary className="cursor-pointer text-sm font-bold text-primary">
                        View field provenance
                      </summary>
                      <div className="mt-3">
                        <ProvenanceList values={fact.provenance} />
                      </div>
                    </details>
                  )}
                </Card>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="career-items-heading">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-extrabold" id="career-items-heading">
              Education, projects, and more
            </h2>
            <p className="mt-1 text-sm text-muted">
              Typed records stay independent from any one resume.
            </p>
          </div>
          <Button
            onClick={() => {
              setEditingItem("new");
              setEditingSkill(undefined);
              setErrors({});
            }}
            variant="secondary"
          >
            <Plus aria-hidden="true" className="size-4" /> Add career record
          </Button>
        </div>
        {editingItem && (
          <Card
            className="mb-4 p-5"
            aria-labelledby="career-item-editor-heading"
          >
            <h3 className="font-extrabold" id="career-item-editor-heading">
              {editingItem === "new"
                ? "Add career record"
                : "Edit career record"}
            </h3>
            <div className="mt-4">
              <FieldErrorSummary errors={errors} ref={errorRef} />
              <CareerItemForm
                errors={errors}
                {...(editingItem === "new" ? {} : { initial: editingItem })}
                loading={saving}
                onCancel={() => setEditingItem(undefined)}
                onSubmit={(input) => void saveItem(input)}
              />
            </div>
          </Card>
        )}
        {items.length === 0 ? (
          <EmptyState
            description="Add education, projects, credentials, publications, awards, volunteering, languages, or portfolio links."
            title="No typed career records yet"
          />
        ) : (
          <ul className="grid gap-3 md:grid-cols-2">
            {items.map((item) => (
              <li key={item.id}>
                <Card className="h-full p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <Badge tone="neutral">{kindLabels[item.kind]}</Badge>
                      <Badge
                        className="ml-2"
                        tone={item.userConfirmed ? "success" : "warning"}
                      >
                        {item.userConfirmed ? "Confirmed" : "Needs review"}
                      </Badge>
                      <h3 className="mt-3 font-extrabold">{item.title}</h3>
                      <p className="mt-1 text-sm text-muted">
                        {item.organization || "Organization not added"}
                      </p>
                    </div>
                    <div className="flex gap-1">
                      <Button
                        aria-label={`Edit ${item.title}`}
                        className="px-3"
                        onClick={() => {
                          setEditingItem(item);
                          setErrors({});
                        }}
                        variant="ghost"
                      >
                        <Pencil aria-hidden="true" className="size-4" />
                      </Button>
                      <Button
                        aria-label={`Delete ${item.title}`}
                        className="px-3"
                        onClick={() => setDeleteItem(item)}
                        variant="ghost"
                      >
                        <Trash2 aria-hidden="true" className="size-4" />
                      </Button>
                    </div>
                  </div>
                  {item.description && (
                    <p className="mt-3 whitespace-pre-wrap text-sm leading-6">
                      {item.description}
                    </p>
                  )}
                  {(item.startDate || item.endDate) && (
                    <p className="mt-3 text-xs text-muted">
                      {item.startDate || "Start not added"} –{" "}
                      {item.endDate || "Present"}
                    </p>
                  )}
                  {item.url && (
                    <a
                      className="mt-3 inline-block text-sm font-bold text-primary"
                      href={item.url}
                      rel="noreferrer"
                      target="_blank"
                    >
                      Open saved link{" "}
                      <span className="sr-only">(opens in a new tab)</span>
                    </a>
                  )}
                  {item.kind === "project" && (
                    <div className="mt-4 rounded-xl border border-line p-3">
                      <p className="text-sm font-extrabold">
                        Related experiences
                      </p>
                      {relationships.some(
                        (relationship) => relationship.projectId === item.id,
                      ) ? (
                        <ul className="mt-2 space-y-2">
                          {relationships
                            .filter(
                              (relationship) =>
                                relationship.projectId === item.id,
                            )
                            .map((relationship) => {
                              const experience = experiences.find(
                                (candidate) =>
                                  candidate.id === relationship.experienceId,
                              );
                              return (
                                <li
                                  className="flex flex-wrap items-center justify-between gap-2 text-sm"
                                  key={relationship.id}
                                >
                                  <span>
                                    {experience
                                      ? `${experience.displayTitle ?? experience.officialTitle} at ${experience.employer}`
                                      : "Related experience"}
                                  </span>
                                  <Button
                                    onClick={() =>
                                      void unlinkProject(relationship)
                                    }
                                    variant="ghost"
                                  >
                                    Remove link
                                  </Button>
                                </li>
                              );
                            })}
                        </ul>
                      ) : (
                        <p className="mt-2 text-xs text-muted">
                          No experience relationship recorded.
                        </p>
                      )}
                      {experiences.length > 0 && (
                        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                          <Select
                            aria-label={`Experience to link to ${item.title}`}
                            onChange={(event) =>
                              setSelectedExperienceByProject((current) => ({
                                ...current,
                                [item.id]: event.target.value,
                              }))
                            }
                            value={selectedExperienceByProject[item.id] ?? ""}
                          >
                            <option value="">Choose experience</option>
                            {experiences.map((experience) => (
                              <option key={experience.id} value={experience.id}>
                                {experience.displayTitle ??
                                  experience.officialTitle}{" "}
                                at {experience.employer}
                              </option>
                            ))}
                          </Select>
                          <Button
                            disabled={
                              !selectedExperienceByProject[item.id] || saving
                            }
                            onClick={() => void linkProject(item)}
                            variant="secondary"
                          >
                            Link experience
                          </Button>
                        </div>
                      )}
                    </div>
                  )}
                  {!item.userConfirmed && (
                    <Button
                      className="mt-4"
                      onClick={() => void confirmItem(item)}
                    >
                      Confirm current facts
                    </Button>
                  )}
                </Card>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="skills-heading">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-extrabold" id="skills-heading">
              Skills
            </h2>
            <p className="mt-1 text-sm text-muted">
              Skill names do not imply evidence or proficiency unless explicitly
              recorded.
            </p>
          </div>
          <Button
            onClick={() => {
              setEditingSkill("new");
              setEditingItem(undefined);
              setErrors({});
            }}
            variant="secondary"
          >
            <Plus aria-hidden="true" className="size-4" /> Add skill
          </Button>
        </div>
        {editingSkill && (
          <Card className="mb-4 p-5" aria-labelledby="skill-editor-heading">
            <h3 className="font-extrabold" id="skill-editor-heading">
              {editingSkill === "new" ? "Add skill" : "Edit skill"}
            </h3>
            <div className="mt-4">
              <FieldErrorSummary errors={errors} ref={errorRef} />
              <SkillForm
                errors={errors}
                {...(editingSkill === "new" ? {} : { initial: editingSkill })}
                loading={saving}
                onCancel={() => setEditingSkill(undefined)}
                onSubmit={(input) => void saveSkill(input)}
              />
            </div>
          </Card>
        )}
        {skills.length === 0 ? (
          <EmptyState
            description="Add only skills you want represented in your structured career record."
            title="No skills added"
          />
        ) : (
          <ul className="flex flex-wrap gap-3">
            {skills.map((skill) => (
              <li
                className="flex items-center gap-2 rounded-xl border border-line bg-surface px-3 py-2"
                key={skill.id}
              >
                <span className="text-sm font-bold">{skill.name}</span>
                {skill.proficiency && (
                  <Badge tone="neutral">{skill.proficiency}</Badge>
                )}
                <Badge tone={skill.userConfirmed ? "success" : "warning"}>
                  {skill.userConfirmed ? "Confirmed" : "Needs review"}
                </Badge>
                {!skill.userConfirmed && (
                  <Button onClick={() => void confirmCurrentSkill(skill)}>
                    Confirm
                  </Button>
                )}
                <Button
                  aria-label={`Edit ${skill.name}`}
                  className="px-3"
                  onClick={() => {
                    setEditingSkill(skill);
                    setErrors({});
                  }}
                  variant="ghost"
                >
                  <Pencil aria-hidden="true" className="size-3.5" />
                </Button>
                <Button
                  aria-label={`Delete ${skill.name}`}
                  className="px-3"
                  onClick={() => setDeleteSkillValue(skill)}
                  variant="ghost"
                >
                  <Trash2 aria-hidden="true" className="size-3.5" />
                </Button>
                {skill.provenance.length > 0 && (
                  <details className="w-full rounded-xl border border-line p-2">
                    <summary className="cursor-pointer text-xs font-bold text-primary">
                      Provenance
                    </summary>
                    <div className="mt-2">
                      <ProvenanceList values={skill.provenance} />
                    </div>
                  </details>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <ConfirmDialog
        confirmLabel="Delete contact fact"
        description="This removes the contact fact from the Career Record. Existing audit history remains."
        loading={saving}
        onConfirm={() => void removeFact()}
        onOpenChange={(open) => {
          if (!open && !saving) setDeleteFact(undefined);
        }}
        open={Boolean(deleteFact)}
        title="Delete this contact fact?"
      />
      <ConfirmDialog
        confirmLabel="Delete career record"
        description="This removes the career-profile record. Linked evidence is preserved and may require conflict review."
        loading={saving}
        onConfirm={() => void removeItem()}
        onOpenChange={(open) => {
          if (!open && !saving) setDeleteItem(undefined);
        }}
        open={Boolean(deleteItem)}
        title="Delete this career record?"
      />
      <ConfirmDialog
        confirmLabel="Delete skill"
        description="This removes the skill from the profile. Linked evidence is preserved rather than silently deleted."
        loading={saving}
        onConfirm={() => void removeSkill()}
        onOpenChange={(open) => {
          if (!open && !saving) setDeleteSkillValue(undefined);
        }}
        open={Boolean(deleteSkillValue)}
        title="Delete this skill?"
      />
    </div>
  );
}
