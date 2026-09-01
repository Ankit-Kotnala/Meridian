"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  Badge,
  Card,
  EmptyState,
  LoadingSkeleton,
  Progress,
  Stepper,
  buttonStyles,
  cn,
} from "@rezumi/ui";

import { getRoleRoadmap } from "../api/career-growth-api";
import type {
  CareerGrowthInsights,
  RoadmapSkill,
  RoleRoadmap,
} from "../api/types";

export function GrowthInsightsPanel({
  insights,
}: {
  insights: CareerGrowthInsights;
}) {
  const [roadmap, setRoadmap] = useState<RoleRoadmap | null>();

  useEffect(() => {
    let cancelled = false;
    void getRoleRoadmap()
      .then((value) => {
        if (!cancelled) setRoadmap(value);
      })
      .catch(() => {
        if (!cancelled) setRoadmap(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const standing = useMemo(
    () => buildStanding(insights, roadmap),
    [insights, roadmap],
  );

  return (
    <section className="space-y-5" aria-labelledby="growth-insights-heading">
      <div>
        <h2
          className="text-lg font-semibold tracking-[-0.02em] text-foreground"
          id="growth-insights-heading"
        >
          Achievement and promotion preparation
        </h2>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
          Compare eligible Career Record evidence with the curated skill path
          for your target role. This is not a labor-market ranking, hiring
          probability, or employer score.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <CoverageMeter
          description="Documented skills with currently eligible evidence"
          done={standing.evidencedSkillCount}
          emptyLabel="No skills documented yet"
          label="Evidence coverage"
          total={standing.documentedSkillCount}
        />
        {roadmap === undefined ? (
          <div
            aria-label="Loading target-role path coverage"
            className="rounded-[var(--radius-card)] border border-line bg-surface p-4"
            role="status"
          >
            <LoadingSkeleton className="min-h-24" />
          </div>
        ) : (
          <CoverageMeter
            description={
              standing.roleTitle
                ? `Path skills for ${standing.roleTitle} with eligible evidence`
                : "Resolve a target role to compare against its path"
            }
            done={standing.evidencedPathCount}
            emptyLabel="No target-role path yet"
            label="Role-path coverage"
            total={standing.pathSkillCount}
          />
        )}
        <CoverageMeter
          description="Promotion-preparation checks currently supported"
          done={standing.supportedCheckCount}
          emptyLabel="No preparation checks"
          label="Preparation checks"
          total={standing.checkCount}
        />
      </div>

      <RoleSkillComparison
        comparisons={standing.pathComparisons}
        extraSkills={standing.offPathSkills}
        loading={roadmap === undefined}
        roleTitle={standing.roleTitle}
      />

      <PromotionPath
        checks={insights.promotionReadiness.checks}
        disclaimer={insights.promotionReadiness.disclaimer}
        generatedAt={insights.promotionReadiness.generatedAt}
        status={insights.promotionReadiness.status}
      />

      <div className="grid gap-5 xl:grid-cols-2">
        <AchievementTimeline achievements={insights.achievements} />
        <SkillEvidenceDashboard skills={insights.skills} />
      </div>

      <AnnualRefreshCard items={insights.annualResumeRefreshes} />
    </section>
  );
}

function buildStanding(
  insights: CareerGrowthInsights,
  roadmap: RoleRoadmap | null | undefined,
) {
  const documentedSkillCount = insights.skills.length;
  const evidencedSkillCount = insights.skills.filter(
    (skill) => skill.evidenceCount > 0,
  ).length;
  const evidencedNames = new Set(
    insights.skills
      .filter((skill) => skill.evidenceCount > 0)
      .map((skill) => normalizeSkillName(skill.name)),
  );
  const pathSkills = roadmap?.stages.flatMap((stage) => stage.skills) ?? [];
  const pathComparisons = pathSkills.map((skill) => ({
    evidenced:
      skill.alreadyDemonstrated ||
      evidencedNames.has(normalizeSkillName(skill.name)),
    skill,
  }));
  const pathNames = new Set(
    pathSkills.map((skill) => normalizeSkillName(skill.name)),
  );
  const offPathSkills = insights.skills.filter(
    (skill) => !pathNames.has(normalizeSkillName(skill.name)),
  );

  return {
    checkCount: insights.promotionReadiness.checks.length,
    documentedSkillCount,
    evidencedPathCount: pathComparisons.filter((item) => item.evidenced).length,
    evidencedSkillCount,
    offPathSkills,
    pathComparisons,
    pathSkillCount: pathSkills.length,
    roleTitle: roadmap?.roleTitle,
    supportedCheckCount: insights.promotionReadiness.checks.filter(
      (check) => check.status === "supported",
    ).length,
  };
}

export function normalizeSkillName(value: string): string {
  return value.trim().replace(/\s+/g, " ").toLocaleLowerCase();
}

function CoverageMeter({
  description,
  done,
  emptyLabel,
  label,
  total,
}: {
  description: string;
  done: number;
  emptyLabel: string;
  label: string;
  total: number;
}) {
  const pct = total === 0 ? null : Math.round((done / total) * 100);
  return (
    <div className="rounded-[var(--radius-card)] border border-line bg-surface p-4">
      <p className="text-[0.6875rem] font-bold uppercase tracking-[0.1em] text-muted">
        {label}
      </p>
      {total === 0 ? (
        <p className="mt-2 text-sm font-semibold text-muted">{emptyLabel}</p>
      ) : (
        <p className="mt-2 text-2xl font-semibold tabular-nums text-foreground">
          {done}
          <span className="text-base font-semibold text-muted">/{total}</span>
        </p>
      )}
      <Progress className="mt-3" label={description} value={pct} />
    </div>
  );
}

function RoleSkillComparison({
  comparisons,
  extraSkills,
  loading,
  roleTitle,
}: {
  comparisons: Array<{ evidenced: boolean; skill: RoadmapSkill }>;
  extraSkills: CareerGrowthInsights["skills"];
  loading: boolean;
  roleTitle: string | undefined;
}) {
  return (
    <Card className="p-5 sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-[0.6875rem] font-bold uppercase tracking-[0.14em] text-primary">
            Skill standing
          </p>
          <h3 className="mt-1 text-lg font-semibold tracking-[-0.02em]">
            {roleTitle
              ? `Your evidence vs the ${roleTitle} path`
              : "Your evidence vs a target-role path"}
          </h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            Each row compares a curated path skill with whether currently
            eligible Career Record evidence supports it. Live job listings are
            in Job Search — Meridian does not invent market percentiles.
          </p>
        </div>
        <Link
          className={cn(buttonStyles.base, buttonStyles.secondary, "shrink-0")}
          href="/job-match"
        >
          Open Job Search
          <ArrowRight aria-hidden="true" className="size-4" />
        </Link>
      </div>

      {loading ? (
        <div
          aria-label="Loading skill standing comparison"
          className="rounded-[var(--radius-card)] border border-line bg-surface p-5"
          role="status"
        >
          <LoadingSkeleton className="min-h-40" />
        </div>
      ) : comparisons.length === 0 ? (
        <EmptyState
          action={
            <Link
              className={cn(buttonStyles.base, buttonStyles.primary)}
              href="/career-profile"
            >
              Review your resume role
              <ArrowRight aria-hidden="true" className="size-4" />
            </Link>
          }
          className="mt-5"
          description="We could not match a curated skill path to the role in your latest resume or Career Record. Review the role title, then return here to compare evidence against that path."
          title="No target-role path to compare yet"
        />
      ) : (
        <ul className="mt-5 grid gap-2">
          {comparisons.map(({ evidenced, skill }) => (
            <li
              className="rounded-[var(--radius-control)] border border-line bg-surface-subtle px-3 py-3"
              key={skill.name}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-foreground">
                  {skill.name}
                </p>
                <Badge tone={evidenced ? "success" : "warning"}>
                  {evidenced ? "Evidence found" : "Gap on this path"}
                </Badge>
              </div>
              <dl className="mt-3 grid gap-2">
                <ComparisonTrack
                  filled
                  label="On the role path"
                  tone="primary"
                />
                <ComparisonTrack
                  filled={evidenced}
                  label="Eligible evidence"
                  tone={evidenced ? "success" : "warning"}
                />
              </dl>
            </li>
          ))}
        </ul>
      )}

      {roleTitle && extraSkills.length > 0 && (
        <div className="mt-5 border-t border-line pt-4">
          <h4 className="text-sm font-semibold text-foreground">
            Documented skills not on this path
          </h4>
          <p className="mt-1 text-xs leading-5 text-muted">
            These remain in your Career Record. They are not treated as missing
            path skills.
          </p>
          <ul className="mt-3 flex flex-wrap gap-2">
            {extraSkills.map((skill) => (
              <li key={skill.skillId}>
                <Badge tone={skill.evidenceCount > 0 ? "success" : "neutral"}>
                  {skill.name}
                  {skill.evidenceCount > 0
                    ? ` · ${skill.evidenceCount} eligible`
                    : " · not demonstrated"}
                </Badge>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

function ComparisonTrack({
  filled,
  label,
  tone,
}: {
  filled: boolean;
  label: string;
  tone: "primary" | "success" | "warning";
}) {
  const fill = {
    primary: "bg-primary",
    success: "bg-success",
    warning: "bg-warning-visual",
  }[tone];
  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-3 text-xs">
        <dt className="font-semibold text-foreground">{label}</dt>
        <dd className="tabular-nums text-muted">
          {filled ? "Present" : "Not found"}
        </dd>
      </div>
      <div
        aria-hidden="true"
        className="h-1.5 overflow-hidden rounded-full bg-surface-inset"
      >
        <div
          className={cn(
            "h-full rounded-full motion-reduce:transition-none",
            fill,
            filled ? "w-full" : "w-[12%]",
          )}
        />
      </div>
    </div>
  );
}

function PromotionPath({
  checks,
  disclaimer,
  generatedAt,
  status,
}: {
  checks: CareerGrowthInsights["promotionReadiness"]["checks"];
  disclaimer: string;
  generatedAt: string;
  status: CareerGrowthInsights["promotionReadiness"]["status"];
}) {
  const stepperSteps = checks.map((check, index) => {
    const priorOpen = checks
      .slice(0, index)
      .some((item) => item.status !== "supported");
    return {
      description:
        check.status === "supported"
          ? `${check.evidenceCount} eligible`
          : humanize(check.status),
      label: check.label,
      state:
        check.status === "supported"
          ? ("complete" as const)
          : priorOpen
            ? ("upcoming" as const)
            : ("current" as const),
    };
  });

  return (
    <Card className="p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[0.6875rem] font-bold uppercase tracking-[0.14em] text-primary">
            Promotion Readiness
          </p>
          <h3 className="mt-1 text-lg font-semibold tracking-[-0.02em]">
            Evidence-backed preparation checklist
          </h3>
        </div>
        <Badge
          tone={
            status === "review_ready"
              ? "success"
              : status === "insufficient_evidence"
                ? "warning"
                : "primary"
          }
        >
          {humanize(status)}
        </Badge>
      </div>
      <p
        className="mt-3 max-w-4xl text-xs font-semibold leading-5 text-muted"
        data-testid="promotion-readiness-disclaimer"
      >
        {disclaimer}
      </p>
      <p className="mt-2 text-xs text-muted">
        Generated {formattedDateTime(generatedAt)}
      </p>
      <Stepper
        className="mt-5"
        label="Promotion preparation path"
        steps={stepperSteps}
      />
      <div className="data-region table-scroll mt-5">
        <table className="min-w-full divide-y divide-line text-left text-sm">
          <caption className="sr-only">
            Promotion preparation checks, evidence state, and next action
          </caption>
          <thead className="bg-surface-subtle text-xs uppercase tracking-wide text-muted">
            <tr>
              <th className="px-4 py-3" scope="col">
                Preparation signal
              </th>
              <th className="px-4 py-3" scope="col">
                State
              </th>
              <th className="px-4 py-3" scope="col">
                Explanation
              </th>
              <th className="px-4 py-3" scope="col">
                Evidence
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {checks.map((check) => (
              <tr key={check.code}>
                <th className="px-4 py-3 font-bold" scope="row">
                  {check.label}
                </th>
                <td className="px-4 py-3">
                  <Badge
                    tone={
                      check.status === "supported"
                        ? "success"
                        : check.status === "needs_evidence"
                          ? "warning"
                          : "neutral"
                    }
                  >
                    {humanize(check.status)}
                  </Badge>
                </td>
                <td className="min-w-72 px-4 py-3 text-muted">
                  {check.explanation}
                </td>
                <td className="px-4 py-3">
                  {check.evidenceCount === 0
                    ? "None linked"
                    : `${check.evidenceCount} eligible`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function AchievementTimeline({
  achievements,
}: {
  achievements: CareerGrowthInsights["achievements"];
}) {
  return (
    <Card className="p-5">
      <h3 className="text-lg font-semibold tracking-[-0.02em]">
        Achievement history
      </h3>
      <p className="mt-1 text-sm text-muted">
        Exact eligible Evidence Vault revisions, newest first.
      </p>
      {achievements.length === 0 ? (
        <EmptyState
          className="mt-4"
          description="Confirm supported achievements in the Evidence Vault to build this history."
          title="No eligible achievements yet"
        />
      ) : (
        <ol className="relative mt-5 space-y-3 border-l border-border-strong pl-5">
          {achievements.map((item) => (
            <li
              className="relative rounded-xl border border-line bg-surface-subtle p-4"
              key={item.evidenceRevisionId}
            >
              <span
                aria-hidden="true"
                className="absolute top-5 -left-[1.45rem] size-2.5 rounded-full border-2 border-success bg-success"
              />
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="success">{humanize(item.strength)}</Badge>
                <Badge>{humanize(item.evidenceType)}</Badge>
                <span className="text-xs text-muted">
                  Revision {item.revisionNumber} ·{" "}
                  {formattedDateTime(item.revisedAt)}
                </span>
              </div>
              <h4 className="mt-2 font-semibold">{item.title}</h4>
              <p className="mt-1 text-sm leading-6">{item.statement}</p>
              <Link
                className="mt-3 inline-flex text-sm font-bold text-primary hover:underline"
                href={`/evidence/${item.evidenceId}`}
              >
                Review exact evidence
              </Link>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

function SkillEvidenceDashboard({
  skills,
}: {
  skills: CareerGrowthInsights["skills"];
}) {
  const categories = useMemo(() => {
    const groups = new Map<string, { evidenced: number; total: number }>();
    for (const skill of skills) {
      const key = skill.category?.trim() || "Uncategorized";
      const current = groups.get(key) ?? { evidenced: 0, total: 0 };
      current.total += 1;
      if (skill.evidenceCount > 0) current.evidenced += 1;
      groups.set(key, current);
    }
    return [...groups.entries()].sort((left, right) =>
      left[0].localeCompare(right[0]),
    );
  }, [skills]);

  return (
    <Card className="p-5">
      <h3 className="text-lg font-semibold tracking-[-0.02em]">
        Skill-evidence dashboard
      </h3>
      <p className="mt-1 text-sm text-muted">
        A skill is demonstrated here only when current eligible evidence is
        linked.
      </p>
      {skills.length === 0 ? (
        <EmptyState
          className="mt-4"
          description="Add skills to your Career Profile and connect eligible evidence."
          title="No documented skills yet"
        />
      ) : (
        <>
          {categories.length > 0 && (
            <ul className="mt-4 grid gap-3">
              {categories.map(([category, counts]) => (
                <li key={category}>
                  <Progress
                    label={`${humanize(category)} · ${counts.evidenced} of ${counts.total} evidenced`}
                    value={Math.round((counts.evidenced / counts.total) * 100)}
                  />
                </li>
              ))}
            </ul>
          )}
          <div className="data-region table-scroll mt-4">
            <table className="min-w-full divide-y divide-line text-left text-sm">
              <caption className="sr-only">
                Documented skills and their eligible evidence coverage
              </caption>
              <thead className="bg-surface-subtle text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="px-4 py-3" scope="col">
                    Skill
                  </th>
                  <th className="px-4 py-3" scope="col">
                    Evidence
                  </th>
                  <th className="px-4 py-3" scope="col">
                    Latest
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {skills.map((skill) => (
                  <tr key={skill.skillId}>
                    <th className="px-4 py-3" scope="row">
                      <span className="font-bold">{skill.name}</span>
                      <span className="block text-xs font-normal text-muted">
                        {skill.category ?? "Uncategorized"} ·{" "}
                        {skill.proficiency
                          ? humanize(skill.proficiency)
                          : "Proficiency not set"}
                      </span>
                    </th>
                    <td className="px-4 py-3">
                      {skill.evidenceCount === 0 ? (
                        <Badge tone="warning">Not demonstrated</Badge>
                      ) : (
                        <Badge tone="success">
                          {skill.evidenceCount} eligible
                        </Badge>
                      )}
                    </td>
                    <td className="px-4 py-3 text-muted">
                      {skill.latestEvidenceAt
                        ? formattedDateTime(skill.latestEvidenceAt)
                        : "No eligible evidence"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  );
}

function AnnualRefreshCard({
  items,
}: {
  items: CareerGrowthInsights["annualResumeRefreshes"];
}) {
  return (
    <Card className="p-5">
      <h3 className="text-lg font-semibold tracking-[-0.02em]">
        Annual resume refresh workflow
      </h3>
      <p className="mt-1 text-sm text-muted">
        Create an Annual resume refresh development item, move it through the
        explicit status controls, and link eligible evidence before marking it
        complete.
      </p>
      {items.length === 0 ? (
        <EmptyState
          className="mt-4"
          description="Use the Development plan form below and choose Annual resume refresh."
          title="No annual refresh scheduled"
        />
      ) : (
        <ul className="mt-4 grid gap-2 sm:grid-cols-2">
          {items.map((item) => (
            <li
              className="rounded-xl border border-line bg-surface-subtle p-4"
              key={item.id}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold">{item.title}</span>
                <Badge
                  tone={
                    item.status === "completed"
                      ? "success"
                      : item.status === "cancelled"
                        ? "neutral"
                        : "primary"
                  }
                >
                  {humanize(item.status)}
                </Badge>
              </div>
              <p className="mt-2 text-xs text-muted">
                Target {formattedDate(item.targetDate)} ·{" "}
                {item.evidenceLinks.length} eligible evidence link(s)
              </p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function humanize(value: string): string {
  return value
    .replaceAll(/([a-z0-9])([A-Z])/g, "$1 $2")
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formattedDate(value: string | null): string {
  if (!value) return "Not set";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(new Date(`${value.slice(0, 10)}T12:00:00Z`));
}

function formattedDateTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
