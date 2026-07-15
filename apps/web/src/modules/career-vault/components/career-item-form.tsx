"use client";

import { type FormEvent } from "react";

import { Button, FieldLabel, Select, TextField } from "@careeros/ui";

import type { CareerItem, CareerItemInput } from "../api/types";
import type { FieldErrors } from "../validation/career-vault-validation";
import { TextareaField } from "./form-controls";

function optional(form: FormData, name: string): string | null {
  return String(form.get(name) ?? "").trim() || null;
}

export function CareerItemForm({
  errors,
  initial,
  loading,
  onCancel,
  onSubmit,
}: {
  errors: FieldErrors;
  initial?: CareerItem;
  loading: boolean;
  onCancel: () => void;
  onSubmit: (input: CareerItemInput) => void;
}) {
  const startIsYearOnly = /^\d{4}$/.test(initial?.startDate ?? "");
  const endIsYearOnly = /^\d{4}$/.test(initial?.endDate ?? "");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onSubmit({
      description: String(form.get("description") ?? "").trim(),
      endDate: optional(form, "endDate"),
      kind: String(form.get("kind")) as CareerItemInput["kind"],
      organization: optional(form, "organization"),
      startDate: optional(form, "startDate"),
      title: String(form.get("title") ?? "").trim(),
      url: optional(form, "url"),
    });
  }

  return (
    <form className="space-y-5" onSubmit={submit}>
      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-2">
          <FieldLabel htmlFor="career-item-kind">Record type</FieldLabel>
          <Select
            defaultValue={initial?.kind ?? "education"}
            id="career-item-kind"
            name="kind"
          >
            <option value="education">Education</option>
            <option value="project">Project</option>
            <option value="credential">Credential</option>
            <option value="publication">Publication</option>
            <option value="award">Award</option>
            <option value="volunteering">Volunteering</option>
            <option value="language">Language</option>
            <option value="portfolio_link">Portfolio link</option>
          </Select>
        </div>
        <TextField
          defaultValue={initial?.title ?? ""}
          error={errors.title}
          id="career-item-title"
          label="Title"
          maxLength={300}
          name="title"
          required
        />
        <TextField
          defaultValue={initial?.organization ?? ""}
          id="career-item-organization"
          label="Organization (optional)"
          maxLength={300}
          name="organization"
        />
        <TextField
          defaultValue={initial?.url ?? ""}
          error={errors.url}
          id="career-item-url"
          label="HTTP(S) URL (optional)"
          name="url"
          type="url"
        />
        <TextField
          defaultValue={initial?.startDate ?? ""}
          error={errors.startDate}
          hint={
            startIsYearOnly
              ? `This source preserves ${initial?.startDate} as year-only. Choose a month to change the record.`
              : "Month and year only."
          }
          id="career-item-start-date"
          label="Start month (optional)"
          name="startDate"
          required={startIsYearOnly}
          type="month"
        />
        <TextField
          defaultValue={initial?.endDate ?? ""}
          error={errors.endDate}
          hint={
            endIsYearOnly
              ? `This source preserves ${initial?.endDate} as year-only. Choose a month to change the record.`
              : "Month and year only."
          }
          id="career-item-end-date"
          label="End month (optional)"
          name="endDate"
          required={endIsYearOnly}
          type="month"
        />
      </div>
      <TextareaField
        defaultValue={initial?.description ?? ""}
        error={errors.description}
        id="career-item-description"
        label="Description (optional)"
        maxLength={8_000}
        name="description"
      />
      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <Button disabled={loading} onClick={onCancel} variant="secondary">
          Cancel
        </Button>
        <Button loading={loading} loadingLabel="Saving record…" type="submit">
          Save record
        </Button>
      </div>
    </form>
  );
}
