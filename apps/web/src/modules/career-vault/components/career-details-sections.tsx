"use client";

import { Pencil, Plus, Trash2 } from "lucide-react";
import { useRef, useState } from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
} from "@careeros/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  ApiRequestError,
  createCareerItem,
  createSkill,
  deleteCareerItem,
  deleteSkill,
  updateCareerItem,
  updateSkill,
} from "../api/career-vault-api";
import type {
  CareerItem,
  CareerItemInput,
  Skill,
  SkillInput,
} from "../api/types";
import {
  type FieldErrors,
  validateCareerItem,
  validateSkill,
} from "../validation/career-vault-validation";
import { CareerItemForm } from "./career-item-form";
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

export function CareerDetailsSections({
  items,
  onItemsChange,
  onSkillsChange,
  skills,
}: {
  items: CareerItem[];
  onItemsChange: (items: CareerItem[]) => void;
  onSkillsChange: (skills: Skill[]) => void;
  skills: Skill[];
}) {
  const [editingItem, setEditingItem] = useState<CareerItem | "new">();
  const [editingSkill, setEditingSkill] = useState<Skill | "new">();
  const [deleteItem, setDeleteItem] = useState<CareerItem>();
  const [deleteSkillValue, setDeleteSkillValue] = useState<Skill>();
  const [errors, setErrors] = useState<FieldErrors>({});
  const [failure, setFailure] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [saving, setSaving] = useState(false);
  const errorRef = useRef<HTMLDivElement>(null);

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
                className="flex items-center gap-2 rounded-xl border border-line bg-white px-3 py-2"
                key={skill.id}
              >
                <span className="text-sm font-bold">{skill.name}</span>
                {skill.proficiency && (
                  <Badge tone="neutral">{skill.proficiency}</Badge>
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
              </li>
            ))}
          </ul>
        )}
      </section>

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
