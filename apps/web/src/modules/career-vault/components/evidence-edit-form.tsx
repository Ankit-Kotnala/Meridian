"use client";

import { type FormEvent } from "react";

import { Button, TextField } from "@rezumi/ui";

import type { EvidenceClaimUpdate, EvidenceItem } from "../api/types";
import type { FieldErrors } from "../validation/career-vault-validation";
import { TextareaField } from "./form-controls";

function optional(form: FormData, name: string): string | null {
  return String(form.get(name) ?? "").trim() || null;
}

export function EvidenceEditForm({
  errors,
  evidence,
  loading,
  onCancel,
  onSubmit,
}: {
  errors: FieldErrors;
  evidence: EvidenceItem;
  loading: boolean;
  onCancel: () => void;
  onSubmit: (input: EvidenceClaimUpdate) => void;
}) {
  const startIsYearOnly = /^\d{4}$/.test(evidence.startDate ?? "");
  const endIsYearOnly = /^\d{4}$/.test(evidence.endDate ?? "");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onSubmit({
      description: String(form.get("description") ?? "").trim(),
      endDate: optional(form, "endDate"),
      organizationOrProject: optional(form, "organizationOrProject"),
      startDate: optional(form, "startDate"),
      title: String(form.get("title") ?? "").trim(),
    });
  }

  return (
    <form className="mt-5 space-y-5" onSubmit={submit}>
      <TextField
        defaultValue={evidence.title}
        error={errors.title}
        id="evidence-edit-title"
        label="Evidence title"
        maxLength={300}
        name="title"
        required
      />
      <TextField
        defaultValue={evidence.organizationOrProject ?? ""}
        id="evidence-edit-organization"
        label="Organization or project (optional)"
        maxLength={300}
        name="organizationOrProject"
      />
      <div className="grid gap-5 sm:grid-cols-2">
        <TextField
          defaultValue={evidence.startDate ?? ""}
          error={errors.startDate}
          hint={
            startIsYearOnly
              ? `This source preserves ${evidence.startDate} as year-only. Choose a month to edit this evidence.`
              : "Month and year only."
          }
          id="evidence-edit-start"
          label="Start month (optional)"
          name="startDate"
          required={startIsYearOnly}
          type="month"
        />
        <TextField
          defaultValue={evidence.endDate ?? ""}
          error={errors.endDate}
          hint={
            endIsYearOnly
              ? `This source preserves ${evidence.endDate} as year-only. Choose a month to edit this evidence.`
              : "Month and year only."
          }
          id="evidence-edit-end"
          label="End month (optional)"
          name="endDate"
          required={endIsYearOnly}
          type="month"
        />
      </div>
      <TextareaField
        defaultValue={evidence.description}
        error={errors.description}
        id="evidence-edit-description"
        label="Description"
        maxLength={8_000}
        name="description"
        required
      />
      <p className="text-xs leading-5 text-muted">
        Source provenance, metrics, and existing links are preserved by this
        edit. Material changes create a new server revision.
      </p>
      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <Button disabled={loading} onClick={onCancel} variant="secondary">
          Cancel
        </Button>
        <Button loading={loading} loadingLabel="Saving evidence…" type="submit">
          Save changes
        </Button>
      </div>
    </form>
  );
}
