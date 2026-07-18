"use client";

import { type FormEvent } from "react";

import { Button, FieldLabel, Select, TextField } from "@careeros/ui";

import type { Skill, SkillInput } from "../api/types";
import type { FieldErrors } from "../validation/career-vault-validation";

export function SkillForm({
  errors,
  initial,
  loading,
  onCancel,
  onSubmit,
}: {
  errors: FieldErrors;
  initial?: Skill;
  loading: boolean;
  onCancel: () => void;
  onSubmit: (input: SkillInput) => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onSubmit({
      category: String(form.get("category") ?? "").trim() || null,
      name: String(form.get("name") ?? "").trim(),
      proficiency: (String(form.get("proficiency") ?? "") ||
        null) as SkillInput["proficiency"],
    });
  }

  return (
    <form className="space-y-5" onSubmit={submit}>
      <div className="grid gap-5 sm:grid-cols-2">
        <TextField
          defaultValue={initial?.name ?? ""}
          error={errors.name}
          id="skill-name"
          label="Skill name"
          maxLength={160}
          name="name"
          required
        />
        <TextField
          defaultValue={initial?.category ?? ""}
          error={errors.category}
          id="skill-category"
          label="Category (optional)"
          maxLength={120}
          name="category"
        />
        <div className="space-y-2 sm:col-span-2">
          <FieldLabel htmlFor="skill-proficiency">
            Proficiency (optional)
          </FieldLabel>
          <Select
            defaultValue={initial?.proficiency ?? ""}
            id="skill-proficiency"
            name="proficiency"
          >
            <option value="">Not specified</option>
            <option value="learning">Learning</option>
            <option value="working">Working</option>
            <option value="advanced">Advanced</option>
            <option value="expert">Expert</option>
          </Select>
        </div>
      </div>
      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <Button disabled={loading} onClick={onCancel} variant="secondary">
          Cancel
        </Button>
        <Button loading={loading} loadingLabel="Saving skill…" type="submit">
          Save skill
        </Button>
      </div>
    </form>
  );
}
