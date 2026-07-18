"use client";

import { useState, type FormEvent } from "react";

import {
  Button,
  CheckboxField,
  FieldLabel,
  Select,
  TextField,
} from "@careeros/ui";

import type { Experience, ExperienceInput, Skill } from "../api/types";
import type { FieldErrors } from "../validation/career-vault-validation";
import { TextareaField } from "./form-controls";

export function ExperienceForm({
  errors,
  experiences,
  initial,
  loading,
  onCancel,
  onSubmit,
  skills,
}: {
  errors: FieldErrors;
  experiences: Experience[];
  initial?: Experience;
  loading: boolean;
  onCancel: () => void;
  onSubmit: (value: ExperienceInput) => void;
  skills: Skill[];
}) {
  const [current, setCurrent] = useState(initial?.current ?? true);
  const startIsYearOnly = /^\d{4}$/.test(initial?.startDate ?? "");
  const endIsYearOnly = /^\d{4}$/.test(initial?.endDate ?? "");
  const relationshipGroupId =
    initial?.promotionGroupId ?? initial?.concurrentGroupId;
  const groupedPeer = relationshipGroupId
    ? experiences.find(
        (experience) =>
          experience.id !== initial?.id &&
          (experience.promotionGroupId === relationshipGroupId ||
            experience.concurrentGroupId === relationshipGroupId),
      )
    : undefined;
  const relationshipOptions = experiences.filter(
    (experience) => experience.id !== initial?.id,
  );

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const optional = (name: string) =>
      String(form.get(name) ?? "").trim() || null;
    onSubmit({
      current,
      description: String(form.get("description") ?? "").trim(),
      displayTitle: optional("displayTitle"),
      employer: String(form.get("employer") ?? "").trim(),
      employmentType: optional("employmentType"),
      endDate: current ? null : optional("endDate"),
      groupWithExperienceId: optional("groupWithExperienceId"),
      location: optional("location"),
      officialTitle: String(form.get("officialTitle") ?? "").trim(),
      skillIds: form.getAll("skillIds").map(String),
      startDate: String(form.get("startDate") ?? "").trim(),
    });
  }

  return (
    <form className="space-y-5" onSubmit={submit}>
      <div className="grid gap-5 sm:grid-cols-2">
        <TextField
          defaultValue={initial?.employer ?? ""}
          error={errors.employer}
          id="experience-employer"
          label="Employer"
          maxLength={240}
          name="employer"
          required
        />
        <TextField
          defaultValue={initial?.officialTitle ?? ""}
          error={errors.officialTitle}
          hint="Use the title recorded by the employer."
          id="experience-official-title"
          label="Official title"
          maxLength={240}
          name="officialTitle"
          required
        />
        <TextField
          defaultValue={initial?.displayTitle ?? ""}
          hint="Optional presentation title; it does not replace the official title."
          id="experience-display-title"
          label="Display title (optional)"
          maxLength={240}
          name="displayTitle"
        />
        <TextField
          defaultValue={initial?.location ?? ""}
          id="experience-location"
          label="Location (optional)"
          maxLength={240}
          name="location"
        />
        <TextField
          defaultValue={initial?.startDate ?? ""}
          error={errors.startDate}
          hint={
            startIsYearOnly
              ? `The imported record preserves ${initial?.startDate} as year-only. Choose a month to edit this record.`
              : "CareerOS stores only the month and year you provide."
          }
          id="experience-start-date"
          label="Start month"
          name="startDate"
          required
          type="month"
        />
        <TextField
          defaultValue={initial?.endDate ?? ""}
          disabled={current}
          error={errors.endDate}
          hint={
            current
              ? "Marked as a current role."
              : endIsYearOnly
                ? `The imported record preserves ${initial?.endDate} as year-only. Choose a month to edit this record.`
                : "Month and year only."
          }
          id="experience-end-date"
          label="End month"
          name="endDate"
          required={!current}
          type="month"
        />
        <div className="space-y-2 sm:col-span-2">
          <FieldLabel htmlFor="experience-employment-type">
            Employment type (optional)
          </FieldLabel>
          <Select
            defaultValue={initial?.employmentType ?? ""}
            id="experience-employment-type"
            name="employmentType"
          >
            <option value="">Not specified</option>
            <option value="full_time">Full-time</option>
            <option value="part_time">Part-time</option>
            <option value="contract">Contract</option>
            <option value="internship">Internship</option>
            <option value="temporary">Temporary</option>
            <option value="volunteer">Volunteer</option>
            <option value="other">Other</option>
          </Select>
        </div>
        <div className="space-y-2 sm:col-span-2">
          <FieldLabel htmlFor="experience-relationship">
            Group with another role (optional)
          </FieldLabel>
          <Select
            aria-describedby="experience-relationship-hint"
            defaultValue={groupedPeer?.id ?? ""}
            id="experience-relationship"
            name="groupWithExperienceId"
          >
            <option value="">No relationship group</option>
            {relationshipOptions.map((experience) => (
              <option key={experience.id} value={experience.id}>
                {experience.displayTitle ?? experience.officialTitle} at{" "}
                {experience.employer}
              </option>
            ))}
          </Select>
          <p
            className="text-xs leading-5 text-muted"
            id="experience-relationship-hint"
          >
            Overlapping roles at the same employer are shown as promotions;
            overlapping roles at different employers are shown as concurrent.
            CareerOS records the relationship without changing your dates or
            titles.
          </p>
        </div>
      </div>
      <CheckboxField
        checked={current}
        id="experience-current"
        label="This is a current role"
        onChange={(event) => setCurrent(event.target.checked)}
      />
      <TextareaField
        defaultValue={initial?.description ?? ""}
        error={errors.description}
        hint="Record only responsibilities and scope you can support."
        id="experience-description"
        label="Description (optional)"
        maxLength={8_000}
        name="description"
      />
      <fieldset className="rounded-2xl border border-line p-4">
        <legend className="px-2 text-sm font-extrabold">Linked skills</legend>
        {skills.length === 0 ? (
          <p className="text-sm text-muted">
            Add skills below, then edit this experience to connect them.
          </p>
        ) : (
          <div className="mt-2 grid gap-3 sm:grid-cols-2">
            {skills.map((skill) => (
              <CheckboxField
                defaultChecked={initial?.skillIds.includes(skill.id)}
                id={`experience-skill-${skill.id}`}
                key={skill.id}
                label={skill.name}
                name="skillIds"
                value={skill.id}
              />
            ))}
          </div>
        )}
      </fieldset>
      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <Button disabled={loading} onClick={onCancel} variant="secondary">
          Cancel
        </Button>
        <Button
          loading={loading}
          loadingLabel="Saving experience…"
          type="submit"
        >
          {initial ? "Save experience" : "Add experience"}
        </Button>
      </div>
    </form>
  );
}
