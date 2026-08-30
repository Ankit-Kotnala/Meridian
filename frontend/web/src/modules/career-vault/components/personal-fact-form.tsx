"use client";

import { type FormEvent } from "react";

import {
  Button,
  CheckboxField,
  FieldLabel,
  Select,
  TextField,
} from "@rezumi/ui";

import type { PersonalFact, PersonalFactInput } from "../api/types";

export const factKindLabels: Record<PersonalFact["kind"], string> = {
  email: "Email",
  link: "Link",
  location: "Location",
  name: "Name",
  phone: "Phone",
};

export function PersonalFactForm({
  initial,
  loading,
  onCancel,
  onSubmit,
}: {
  initial?: PersonalFact;
  loading: boolean;
  onCancel: () => void;
  onSubmit: (input: PersonalFactInput) => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onSubmit({
      isPrimary: form.get("isPrimary") === "on",
      // The fact type is immutable once stored: changing it would silently
      // reinterpret the value rather than record a new fact.
      kind: initial
        ? initial.kind
        : (String(form.get("kind")) as PersonalFact["kind"]),
      label: String(form.get("label") ?? "").trim() || null,
      value: String(form.get("value") ?? "").trim(),
    });
  }

  return (
    <form className="space-y-5" onSubmit={submit}>
      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-2">
          <FieldLabel htmlFor="personal-fact-kind">Fact type</FieldLabel>
          <Select
            defaultValue={initial?.kind ?? "name"}
            disabled={Boolean(initial)}
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
          defaultValue={initial?.label ?? ""}
          id="personal-fact-label"
          label="Label (optional)"
          maxLength={80}
          name="label"
        />
      </div>
      <TextField
        defaultValue={initial?.value ?? ""}
        id="personal-fact-value"
        label="Value"
        maxLength={2_048}
        name="value"
        required
      />
      <CheckboxField
        defaultChecked={initial?.isPrimary ?? false}
        id="personal-fact-primary"
        label="Use as the primary value for this fact type"
        name="isPrimary"
      />
      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <Button disabled={loading} onClick={onCancel} variant="secondary">
          Cancel
        </Button>
        <Button
          loading={loading}
          loadingLabel="Saving contact fact…"
          type="submit"
        >
          Save contact fact
        </Button>
      </div>
    </form>
  );
}
