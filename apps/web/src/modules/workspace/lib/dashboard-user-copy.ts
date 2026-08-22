import type { DashboardResumeHealth } from "../components/dashboard-resume-state";
import type { DashboardCount, DashboardSummary } from "../server/dashboard-summary";

function countValue(count: DashboardCount): number | null {
  if (count.kind === "unavailable") return null;
  return count.value;
}

function plural(value: number, singular: string, pluralForm: string): string {
  return value === 1 ? singular : pluralForm;
}

/** One-line hero subtitle: what the user has, or what to do next. */
export function heroSubtitle(
  summary: DashboardSummary,
  resumeHealth: DashboardResumeHealth,
): string {
  const roles = countValue(summary.record.experiences);
  const skills = countValue(summary.record.skills);
  const evidence = countValue(summary.record.evidence);
  const achievements = countValue(summary.record.achievements);
  const pending = countValue(summary.activation.pendingImports);
  const attentionCount = summary.attention.length;

  if (attentionCount > 0) {
    return `${attentionCount} ${plural(attentionCount, "item needs", "items need")} your review — deadlines, drafts, and facts waiting on you.`;
  }

  if (pending !== null && pending > 0) {
    return `${pending} ${plural(pending, "fact from your resume is", "facts from your resume are")} waiting for you to accept or reject.`;
  }

  if (resumeHealth.kind === "review") {
    return "Your resume was parsed — confirm the fields so they can land on your profile.";
  }

  if (resumeHealth.kind === "report" && resumeHealth.score !== null) {
    return `Your latest resume report scored ${resumeHealth.score}/100. Open it to see what to improve.`;
  }

  if (resumeHealth.kind === "processing") {
    return "Your resume is being scanned and parsed. This usually takes a minute.";
  }

  const profileParts: string[] = [];
  if (roles !== null && roles > 0) {
    profileParts.push(`${roles} ${plural(roles, "role", "roles")}`);
  }
  if (skills !== null && skills > 0) {
    profileParts.push(`${skills} ${plural(skills, "skill", "skills")}`);
  }
  if (evidence !== null && evidence > 0) {
    profileParts.push(`${evidence} ${plural(evidence, "evidence item", "evidence items")}`);
  }
  if (achievements !== null && achievements > 0) {
    profileParts.push(
      `${achievements} open ${plural(achievements, "achievement", "achievements")}`,
    );
  }

  if (profileParts.length > 0) {
    return `Your profile includes ${profileParts.join(", ")}.`;
  }

  if (summary.pipeline.kind === "ready" && summary.pipeline.total > 0) {
    const total = summary.pipeline.total;
    return `You are tracking ${total} ${plural(total, "application", "applications")} across your pipeline.`;
  }

  return "Add your work history or upload a resume to start matching roles and preparing applications.";
}

/** Short footnote under career-record stats when counts are loaded. */
export function recordStatsFootnote(record: DashboardSummary["record"]): string | null {
  const roles = countValue(record.experiences);
  const skills = countValue(record.skills);
  const evidence = countValue(record.evidence);
  const achievements = countValue(record.achievements);

  if (
    roles === null ||
    skills === null ||
    evidence === null ||
    achievements === null
  ) {
    return null;
  }

  if (roles === 0 && skills === 0 && evidence === 0 && achievements === 0) {
    return "Your profile is empty — add a role or upload a resume to get started.";
  }

  const parts: string[] = [];
  if (achievements > 0) {
    parts.push(
      `${achievements} ${plural(achievements, "achievement", "achievements")} still open`,
    );
  }
  if (evidence > 0 && (record.evidenceConfirmed.kind !== "count" || record.evidenceConfirmed.value < evidence)) {
    const confirmed =
      record.evidenceConfirmed.kind === "count" ? record.evidenceConfirmed.value : 0;
    const unconfirmed = Math.max(evidence - confirmed, 0);
    if (unconfirmed > 0) {
      parts.push(
        `${unconfirmed} ${plural(unconfirmed, "evidence item", "evidence items")} not yet confirmed`,
      );
    }
  }

  if (parts.length === 0) {
    return "Everything here links to the detail view where you can edit or add more.";
  }

  return parts.join(" · ");
}
