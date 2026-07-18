"use client";

import { type FormEvent } from "react";

import {
  Button,
  CheckboxField,
  FieldLabel,
  Select,
  TextField,
} from "@careeros/ui";

import type { EvidenceInput, Experience, Skill } from "../api/types";
import type { FieldErrors } from "../validation/career-vault-validation";
import { TextareaField } from "./form-controls";

function optional(form: FormData, name: string): string | null {
  return String(form.get(name) ?? "").trim() || null;
}

export function EvidenceForm({
  errors,
  experiences,
  loading,
  onCancel,
  onSubmit,
  skills,
}: {
  errors: FieldErrors;
  experiences: Experience[];
  loading: boolean;
  onCancel: () => void;
  onSubmit: (value: EvidenceInput) => void;
  skills: Skill[];
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const metric = {
      attribution: String(form.get("metricAttribution") ?? "individual") as
        "individual" | "shared" | "team",
      baseline: optional(form, "metricBaseline"),
      comparator: optional(form, "metricComparator"),
      name: String(form.get("metricName") ?? "").trim(),
      periodEnd: optional(form, "metricPeriodEnd"),
      periodStart: String(form.get("metricPeriodStart") ?? "").trim(),
      precision: String(form.get("metricPrecision") ?? "exact") as
        "approximate" | "exact",
      unit: String(form.get("metricUnit") ?? "").trim(),
      value: String(form.get("metricValue") ?? "").trim(),
    };
    const hasMetric = Boolean(
      metric.name ||
      metric.value ||
      metric.unit ||
      metric.periodStart ||
      metric.baseline ||
      metric.comparator,
    );
    onSubmit({
      attachmentIds: [],
      description: String(form.get("description") ?? "").trim(),
      endDate: optional(form, "endDate"),
      experienceIds: form.getAll("experienceIds").map(String),
      metrics: hasMetric ? [metric] : [],
      organizationOrProject: optional(form, "organizationOrProject"),
      skillIds: form.getAll("skillIds").map(String),
      source: {
        blockId: null,
        documentId: null,
        end: null,
        page: null,
        snapshotId: null,
        sourceType: "manual",
        start: null,
        url: null,
      },
      startDate: optional(form, "startDate"),
      title: String(form.get("title") ?? "").trim(),
      type: String(form.get("type") ?? ""),
    });
  }

  return (
    <form className="space-y-6" onSubmit={submit}>
      <div className="grid gap-5 sm:grid-cols-2">
        <TextField
          error={errors.title}
          id="evidence-title"
          label="Evidence title"
          maxLength={300}
          name="title"
          required
        />
        <TextField
          id="evidence-organization"
          label="Organization or project (optional)"
          maxLength={300}
          name="organizationOrProject"
        />
        <div className="space-y-2">
          <FieldLabel htmlFor="evidence-type">Evidence type</FieldLabel>
          <Select
            aria-invalid={Boolean(errors.type)}
            defaultValue=""
            id="evidence-type"
            name="type"
            required
          >
            <option disabled value="">
              Choose a type
            </option>
            <option value="resume_statement">Resume statement</option>
            <option value="user_confirmed_achievement">
              User-confirmed achievement
            </option>
            <option value="metric">Metric</option>
            <option value="project">Project</option>
            <option value="certificate">Certificate</option>
            <option value="publication">Publication</option>
            <option value="award">Award</option>
            <option value="performance_review_excerpt">
              Performance-review excerpt
            </option>
            <option value="portfolio_link">Portfolio link</option>
            <option value="github_link">GitHub link</option>
            <option value="testimonial">Testimonial</option>
            <option value="supporting_document">Supporting document</option>
            <option value="user_note">User note</option>
          </Select>
          {errors.type && (
            <p className="text-xs font-semibold text-danger">{errors.type}</p>
          )}
        </div>
        <div className="rounded-xl border border-line bg-slate-50 p-3 text-sm">
          <p className="font-bold">Source: manual entry</p>
          <p className="mt-1 text-xs leading-5 text-muted">
            Resume and attachment provenance can only be created through their
            reviewed import or upload workflows.
          </p>
        </div>
        <TextField
          error={errors.startDate}
          hint="Month and year only."
          id="evidence-start-date"
          label="Start month (optional)"
          name="startDate"
          type="month"
        />
        <TextField
          error={errors.endDate}
          hint="Month and year only."
          id="evidence-end-date"
          label="End month (optional)"
          name="endDate"
          type="month"
        />
      </div>
      <TextareaField
        error={errors.description}
        hint="Describe only what you can support. Confirmation and verification are separate actions."
        id="evidence-description"
        label="Description"
        maxLength={8_000}
        name="description"
        required
      />

      <fieldset className="rounded-2xl border border-line p-4 sm:p-5">
        <legend className="px-2 text-sm font-extrabold">
          Metric details (optional)
        </legend>
        <p className="mb-4 text-xs leading-5 text-muted">
          A numeric claim needs a measured result, unit, period, precision, and
          attribution. Eligibility remains server-authoritative.
        </p>
        <div className="grid gap-5 sm:grid-cols-2">
          <TextField
            error={errors.metric0Name}
            id="metric-name"
            label="Result measured"
            maxLength={160}
            name="metricName"
          />
          <TextField
            error={errors.metric0Value}
            id="metric-value"
            label="Value"
            name="metricValue"
          />
          <TextField
            error={errors.metric0Unit}
            id="metric-unit"
            label="Unit"
            maxLength={80}
            name="metricUnit"
          />
          <TextField
            error={errors.metric0PeriodStart}
            id="metric-period-start"
            label="Period start"
            name="metricPeriodStart"
            type="month"
          />
          <TextField
            error={errors.metric0PeriodEnd}
            id="metric-period-end"
            label="Period end (optional)"
            name="metricPeriodEnd"
            type="month"
          />
          <TextField
            error={errors.metric0Baseline}
            id="metric-baseline"
            label="Baseline (optional)"
            maxLength={500}
            name="metricBaseline"
          />
          <TextField
            id="metric-comparator"
            label="Comparator (optional)"
            maxLength={240}
            name="metricComparator"
          />
          <div className="space-y-2">
            <FieldLabel htmlFor="metric-precision">Precision</FieldLabel>
            <Select
              defaultValue="exact"
              id="metric-precision"
              name="metricPrecision"
            >
              <option value="exact">Exact</option>
              <option value="approximate">Approximate</option>
            </Select>
          </div>
          <div className="space-y-2">
            <FieldLabel htmlFor="metric-attribution">Attribution</FieldLabel>
            <Select
              defaultValue="individual"
              id="metric-attribution"
              name="metricAttribution"
            >
              <option value="individual">Individual</option>
              <option value="team">Team</option>
              <option value="shared">Shared</option>
            </Select>
          </div>
        </div>
      </fieldset>

      <fieldset className="rounded-2xl border border-line p-4 sm:p-5">
        <legend className="px-2 text-sm font-extrabold">
          Connect to career record
        </legend>
        <div className="mt-2 grid gap-5 sm:grid-cols-2">
          <div>
            <p className="mb-3 text-sm font-bold">Experiences</p>
            {experiences.length === 0 ? (
              <p className="text-sm text-muted">
                No experiences are available.
              </p>
            ) : (
              experiences.map((experience) => (
                <CheckboxField
                  id={`evidence-experience-${experience.id}`}
                  key={experience.id}
                  label={`${experience.displayTitle || experience.officialTitle} at ${experience.employer}`}
                  name="experienceIds"
                  value={experience.id}
                />
              ))
            )}
          </div>
          <div>
            <p className="mb-3 text-sm font-bold">Skills</p>
            {skills.length === 0 ? (
              <p className="text-sm text-muted">No skills are available.</p>
            ) : (
              skills.map((skill) => (
                <CheckboxField
                  id={`evidence-skill-${skill.id}`}
                  key={skill.id}
                  label={skill.name}
                  name="skillIds"
                  value={skill.id}
                />
              ))
            )}
          </div>
        </div>
      </fieldset>

      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <Button disabled={loading} onClick={onCancel} variant="secondary">
          Cancel
        </Button>
        <Button loading={loading} loadingLabel="Saving evidence…" type="submit">
          Save evidence
        </Button>
      </div>
    </form>
  );
}
