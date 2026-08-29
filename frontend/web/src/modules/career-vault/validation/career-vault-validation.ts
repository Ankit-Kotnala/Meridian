import type {
  AchievementInput,
  CareerItemInput,
  CareerProfileUpdate,
  EvidenceInput,
  EvidenceClaimUpdate,
  EvidenceMetric,
  ExperienceInput,
  SkillInput,
} from "../api/types";

export type FieldErrors = Record<string, string>;

const YEAR_MONTH = /^(19|20|21)\d{2}-(0[1-9]|1[0-2])$/;

export function commaSeparated(value: string): string[] {
  return Array.from(
    new Set(
      value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  );
}

export function validateCareerProfile(value: CareerProfileUpdate): FieldErrors {
  const errors: FieldErrors = {};
  if (value.professionalHeadline.length > 240) {
    errors.professionalHeadline = "Use 240 characters or fewer.";
  }
  if (value.professionalSummary.length > 4_000) {
    errors.professionalSummary = "Use 4,000 characters or fewer.";
  }
  if (value.workAuthorization.length > 500) {
    errors.workAuthorization = "Use 500 characters or fewer.";
  }
  return errors;
}

export function validateExperience(value: ExperienceInput): FieldErrors {
  const errors: FieldErrors = {};
  if (!value.employer.trim()) errors.employer = "Enter the employer.";
  if (!value.officialTitle.trim()) {
    errors.officialTitle = "Enter the official title.";
  }
  if (!YEAR_MONTH.test(value.startDate)) {
    errors.startDate = "Choose a start month and year.";
  }
  if (value.endDate && !YEAR_MONTH.test(value.endDate)) {
    errors.endDate = "Choose an end month and year.";
  }
  if (value.current && value.endDate) {
    errors.endDate = "A current role cannot have an end month.";
  }
  if (
    YEAR_MONTH.test(value.startDate) &&
    value.endDate &&
    YEAR_MONTH.test(value.endDate) &&
    value.endDate < value.startDate
  ) {
    errors.endDate = "End month cannot be before the start month.";
  }
  if (value.description.length > 8_000) {
    errors.description = "Use 8,000 characters or fewer.";
  }
  return errors;
}

function metricErrors(
  metric: Omit<EvidenceMetric, "id">,
  prefix = "metric",
): FieldErrors {
  const errors: FieldErrors = {};
  const started = Boolean(
    metric.name.trim() ||
    metric.value.trim() ||
    metric.unit.trim() ||
    metric.periodStart.trim() ||
    metric.baseline?.trim() ||
    metric.comparator?.trim(),
  );
  if (!started) return errors;
  if (!metric.name.trim())
    errors[`${prefix}Name`] = "Name the result being measured.";
  if (!metric.value.trim())
    errors[`${prefix}Value`] = "Enter the measured value.";
  if (!/^-?\d{1,14}(?:\.\d{1,4})?$/.test(metric.value.trim())) {
    errors[`${prefix}Value`] =
      "Enter a number with no more than four decimal places.";
  }
  if (!metric.unit.trim()) errors[`${prefix}Unit`] = "Enter the unit.";
  if (!YEAR_MONTH.test(metric.periodStart)) {
    errors[`${prefix}PeriodStart`] = "Choose the period start month.";
  }
  if (metric.periodEnd && !YEAR_MONTH.test(metric.periodEnd)) {
    errors[`${prefix}PeriodEnd`] = "Choose a valid period end month.";
  }
  if (metric.periodEnd && metric.periodEnd < metric.periodStart) {
    errors[`${prefix}PeriodEnd`] = "Period end cannot precede its start.";
  }
  return errors;
}

export function validateEvidence(value: EvidenceInput): FieldErrors {
  const errors: FieldErrors = {};
  if (!value.title.trim()) errors.title = "Enter an evidence title.";
  if (!value.description.trim()) {
    errors.description = "Describe exactly what the source supports.";
  } else if (value.description.length > 8_000) {
    errors.description = "Use 8,000 characters or fewer.";
  }
  if (!value.type) errors.type = "Choose an evidence type.";
  if (value.source.sourceType !== "manual") {
    errors.sourceType = "Manual entry can only use a manual source.";
  }
  if (value.startDate && !YEAR_MONTH.test(value.startDate)) {
    errors.startDate = "Choose a valid start month.";
  }
  if (value.endDate && !value.startDate) {
    errors.endDate = "Add a start month before an end month.";
  } else if (value.endDate && !YEAR_MONTH.test(value.endDate)) {
    errors.endDate = "Choose a valid end month.";
  } else if (
    value.startDate &&
    value.endDate &&
    value.endDate < value.startDate
  ) {
    errors.endDate = "End month cannot precede its start.";
  }
  value.metrics.forEach((metric, index) => {
    Object.assign(errors, metricErrors(metric, `metric${index}`));
  });
  return errors;
}

export function validateEvidenceUpdate(
  value: EvidenceClaimUpdate,
): FieldErrors {
  const errors: FieldErrors = {};
  if (!value.title.trim()) errors.title = "Enter an evidence title.";
  if (!value.description.trim()) {
    errors.description = "Describe exactly what the source supports.";
  } else if (value.description.length > 8_000) {
    errors.description = "Use 8,000 characters or fewer.";
  }
  if (value.startDate && !YEAR_MONTH.test(value.startDate)) {
    errors.startDate = "Choose a valid start month.";
  }
  if (value.endDate && !value.startDate) {
    errors.endDate = "Add a start month before an end month.";
  } else if (value.endDate && !YEAR_MONTH.test(value.endDate)) {
    errors.endDate = "Choose a valid end month.";
  } else if (
    value.startDate &&
    value.endDate &&
    value.endDate < value.startDate
  ) {
    errors.endDate = "End month cannot precede its start.";
  }
  return errors;
}

export function validateCareerItem(value: CareerItemInput): FieldErrors {
  const errors: FieldErrors = {};
  if (!value.title.trim()) errors.title = "Enter a title.";
  if (value.description.length > 8_000) {
    errors.description = "Use 8,000 characters or fewer.";
  }
  if (value.startDate && !YEAR_MONTH.test(value.startDate)) {
    errors.startDate = "Choose a valid start month.";
  }
  if (value.endDate && !value.startDate) {
    errors.endDate = "Add a start month before an end month.";
  } else if (value.endDate && !YEAR_MONTH.test(value.endDate)) {
    errors.endDate = "Choose a valid end month.";
  } else if (
    value.startDate &&
    value.endDate &&
    value.endDate < value.startDate
  ) {
    errors.endDate = "End month cannot precede its start.";
  }
  if (value.kind === "portfolio_link" && !value.url) {
    errors.url = "Enter the portfolio URL.";
  } else if (value.url) {
    try {
      const url = new URL(value.url);
      if (!new Set(["http:", "https:"]).has(url.protocol)) throw new Error();
    } catch {
      errors.url = "Enter a valid HTTP(S) URL.";
    }
  }
  return errors;
}

export function validateSkill(value: SkillInput): FieldErrors {
  const errors: FieldErrors = {};
  if (!value.name.trim()) errors.name = "Enter the skill name.";
  if (value.name.length > 160) errors.name = "Use 160 characters or fewer.";
  if ((value.category?.length ?? 0) > 120) {
    errors.category = "Use 120 characters or fewer.";
  }
  return errors;
}

export function validateAchievementDraft(value: AchievementInput): FieldErrors {
  const errors: FieldErrors = {};
  if (!value.title.trim()) errors.title = "Give this draft a short title.";
  if (value.title.length > 300) errors.title = "Use 300 characters or fewer.";
  for (const [name, answer] of Object.entries(value.answers)) {
    if (answer.length > 2_000) {
      errors[name] = "Use 2,000 characters or fewer.";
    }
  }
  if (value.metric) Object.assign(errors, metricErrors(value.metric));
  return errors;
}

export function validateAchievementConversion(
  value: AchievementInput,
): FieldErrors {
  const errors = validateAchievementDraft(value);
  if (!value.answers.delivered.trim()) {
    errors.delivered = "Answer what you delivered before converting.";
  }
  if (!value.answers.problem.trim()) {
    errors.problem = "Answer what problem you addressed before converting.";
  }
  if (!value.answers.changed.trim()) {
    errors.changed =
      "Answer what changed, or state that the outcome is not known yet.";
  }
  return errors;
}

export function isResourceId(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    value,
  );
}
