"use client";

import { ArrowRight, CheckCircle2, CircleDashed } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";

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

type PathComparison = {
  evidenced: boolean;
  skill: RoadmapSkill;
  stageName: string;
};

type SkillFilter = "all" | "evidenced" | "gaps";

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
    <section className="space-y-4" aria-labelledby="growth-insights-heading">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <h2
            className="text-lg font-semibold tracking-[-0.02em] text-foreground"
            id="growth-insights-heading"
          >
            Achievement and promotion preparation
          </h2>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
            Compare eligible Career Record evidence with the curated skill path
            for your target role. Not a labor-market ranking or employer score.
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

      <CoverageStrip
        documented={standing.documentedSkillCount}
        evidenced={standing.evidencedSkillCount}
        loading={roadmap === undefined}
        pathDone={standing.evidencedPathCount}
        pathTotal={standing.pathSkillCount}
        preparationDone={standing.supportedCheckCount}
        preparationTotal={standing.checkCount}
        roleTitle={standing.roleTitle}
      />

      <SkillPathMatrix
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

      <div className="grid gap-4 xl:grid-cols-2">
        <CollapsibleSection
          defaultOpen={insights.achievements.length > 0}
          summary={`Achievement history · ${insights.achievements.length}`}
        >
          <AchievementTimeline achievements={insights.achievements} />
        </CollapsibleSection>
        <CollapsibleSection
          defaultOpen={insights.skills.length > 0}
          summary={`Documented skills · ${insights.skills.length}`}
        >
          <SkillEvidenceDashboard skills={insights.skills} />
        </CollapsibleSection>
      </div>

      {insights.annualResumeRefreshes.length > 0 && (
        <AnnualRefreshCard items={insights.annualResumeRefreshes} />
      )}
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
  const pathComparisons: PathComparison[] =
    roadmap?.stages.flatMap((stage) =>
      stage.skills.map((skill) => ({
        evidenced:
          skill.alreadyDemonstrated ||
          evidencedNames.has(normalizeSkillName(skill.name)),
        skill,
        stageName: stage.stage,
      })),
    ) ?? [];
  const pathNames = new Set(
    pathComparisons.map((item) => normalizeSkillName(item.skill.name)),
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
    pathSkillCount: pathComparisons.length,
    roleTitle: roadmap?.roleTitle,
    supportedCheckCount: insights.promotionReadiness.checks.filter(
      (check) => check.status === "supported",
    ).length,
  };
}

export function normalizeSkillName(value: string): string {
  return value.trim().replace(/\s+/g, " ").toLocaleLowerCase();
}

function CoverageStrip({
  documented,
  evidenced,
  loading,
  pathDone,
  pathTotal,
  preparationDone,
  preparationTotal,
  roleTitle,
}: {
  documented: number;
  evidenced: number;
  loading: boolean;
  pathDone: number;
  pathTotal: number;
  preparationDone: number;
  preparationTotal: number;
  roleTitle: string | undefined;
}) {
  const pathPct =
    pathTotal === 0 ? null : Math.round((pathDone / pathTotal) * 100);
  const prepPct =
    preparationTotal === 0
      ? null
      : Math.round((preparationDone / preparationTotal) * 100);
  const docPct =
    documented === 0 ? null : Math.round((evidenced / documented) * 100);

  return (
    <div className="grid gap-2 sm:grid-cols-3">
      <CoverageTile
        detail="Skills with eligible evidence in your Career Record"
        emptyLabel="No skills documented"
        label="Evidence coverage"
        pct={docPct}
        value={
          documented === 0 ? "—" : `${evidenced}/${documented} skills evidenced`
        }
      />
      {loading ? (
        <div
          aria-label="Loading target-role path coverage"
          className="rounded-[var(--radius-card)] border border-line bg-surface px-4 py-3"
          role="status"
        >
          <LoadingSkeleton className="min-h-14" />
        </div>
      ) : (
        <CoverageTile
          detail={
            roleTitle
              ? `Path skills for ${roleTitle} with eligible evidence`
              : "Resolve a target role to compare against its path"
          }
          emptyLabel="No target-role path yet"
          label="Role-path coverage"
          pct={pathPct}
          value={
            pathTotal === 0
              ? "—"
              : `${pathDone}/${pathTotal} path skills evidenced`
          }
        />
      )}
      <CoverageTile
        detail="Promotion-preparation checks currently supported"
        emptyLabel="No preparation checks"
        label="Preparation checks"
        pct={prepPct}
        value={
          preparationTotal === 0
            ? "—"
            : `${preparationDone}/${preparationTotal} checks supported`
        }
      />
    </div>
  );
}

function CoverageTile({
  detail,
  emptyLabel,
  label,
  pct,
  value,
}: {
  detail: string;
  emptyLabel: string;
  label: string;
  pct: number | null;
  value: string;
}) {
  return (
    <div className="rounded-[var(--radius-card)] border border-line bg-surface px-4 py-3">
      <p className="text-[0.6875rem] font-bold uppercase tracking-[0.1em] text-muted">
        {label}
      </p>
      <p className="mt-1 text-sm font-semibold text-foreground">
        {value === "—" ? emptyLabel : value}
      </p>
      {pct !== null ? (
        <Progress className="mt-2" label={detail} value={pct} />
      ) : (
        <p className="mt-2 text-xs leading-5 text-muted">{detail}</p>
      )}
    </div>
  );
}

function SkillPathMatrix({
  comparisons,
  extraSkills,
  loading,
  roleTitle,
}: {
  comparisons: PathComparison[];
  extraSkills: CareerGrowthInsights["skills"];
  loading: boolean;
  roleTitle: string | undefined;
}) {
  const [filter, setFilter] = useState<SkillFilter>("all");
  const gapCount = comparisons.filter((item) => !item.evidenced).length;
  const evidencedCount = comparisons.length - gapCount;

  const filtered = useMemo(() => {
    if (filter === "gaps") {
      return comparisons.filter((item) => !item.evidenced);
    }
    if (filter === "evidenced") {
      return comparisons.filter((item) => item.evidenced);
    }
    return comparisons;
  }, [comparisons, filter]);

  const grouped = useMemo(() => {
    const groups = new Map<string, PathComparison[]>();
    for (const item of filtered) {
      const bucket = groups.get(item.stageName) ?? [];
      bucket.push(item);
      groups.set(item.stageName, bucket);
    }
    return [...groups.entries()];
  }, [filtered]);

  return (
    <Card className="p-4 sm:p-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="text-[0.6875rem] font-bold uppercase tracking-[0.14em] text-primary">
            Skill standing
          </p>
          <h3 className="mt-1 text-base font-semibold tracking-[-0.02em] sm:text-lg">
            {roleTitle
              ? `${roleTitle} path · ${evidencedCount} evidenced · ${gapCount} gaps`
              : "Your evidence vs a target-role path"}
          </h3>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-muted sm:text-sm sm:leading-6">
            Each skill shows whether eligible Career Record evidence supports it.
            Expand a gap to see why it matters and a first step.
          </p>
        </div>
        {comparisons.length > 0 && (
          <div
            aria-label="Filter path skills"
            className="flex flex-wrap gap-2"
            role="group"
          >
            <FilterChip
              active={filter === "all"}
              label={`All (${comparisons.length})`}
              onClick={() => setFilter("all")}
            />
            <FilterChip
              active={filter === "gaps"}
              label={`Gaps (${gapCount})`}
              onClick={() => setFilter("gaps")}
            />
            <FilterChip
              active={filter === "evidenced"}
              label={`Evidenced (${evidencedCount})`}
              onClick={() => setFilter("evidenced")}
            />
          </div>
        )}
      </div>

      {loading ? (
        <div
          aria-label="Loading skill standing comparison"
          className="mt-4 rounded-[var(--radius-card)] border border-line bg-surface-subtle p-4"
          role="status"
        >
          <LoadingSkeleton className="min-h-32" />
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
          className="mt-4"
          description="We could not match a curated skill path to the role in your latest resume or Career Record."
          title="No target-role path to compare yet"
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          className="mt-4"
          description="Switch filters to see other path skills."
          title={`No ${filter === "gaps" ? "gaps" : "evidenced skills"} in this view`}
        />
      ) : (
        <div className="mt-4 max-h-[min(28rem,70vh)] space-y-4 overflow-y-auto pr-1">
          {grouped.map(([stageName, items]) => (
            <section key={stageName}>
              <h4 className="sticky top-0 z-[1] bg-surface/95 py-1 text-[0.6875rem] font-bold uppercase tracking-[0.12em] text-muted backdrop-blur-sm">
                {stageName}
              </h4>
              <ul className="mt-1 grid gap-1.5 sm:grid-cols-2 xl:grid-cols-3">
                {items.map(({ evidenced, skill }) => (
                  <SkillPathCell
                    evidenced={evidenced}
                    key={`${stageName}-${skill.name}`}
                    skill={skill}
                  />
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}

      {roleTitle && extraSkills.length > 0 && (
        <div className="mt-4 border-t border-line pt-3">
          <p className="text-xs font-semibold text-foreground">
            Documented off-path skills ({extraSkills.length})
          </p>
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {extraSkills.map((skill) => (
              <li key={skill.skillId}>
                <Badge tone={skill.evidenceCount > 0 ? "success" : "neutral"}>
                  {skill.name}
                  {skill.evidenceCount > 0
                    ? ` · ${skill.evidenceCount} eligible`
                    : ""}
                </Badge>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

function FilterChip({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      aria-pressed={active}
      className={cn(
        "rounded-[var(--radius-pill)] border px-2.5 py-1 text-xs font-semibold transition-colors",
        active
          ? "border-primary bg-primary-soft text-primary"
          : "border-line bg-surface-subtle text-muted hover:border-primary/30 hover:text-foreground",
      )}
      onClick={onClick}
      type="button"
    >
      {label}
    </button>
  );
}

function SkillPathCell({
  evidenced,
  skill,
}: {
  evidenced: boolean;
  skill: RoadmapSkill;
}) {
  const Icon = evidenced ? CheckCircle2 : CircleDashed;
  const content = (
    <>
      <Icon
        aria-hidden="true"
        className={cn(
          "mt-0.5 size-4 shrink-0",
          evidenced ? "text-success" : "text-warning-visual",
        )}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-semibold leading-5 text-foreground">
            {skill.name}
          </p>
          <Badge className="shrink-0" tone={evidenced ? "success" : "warning"}>
            {evidenced ? "Evidence found" : "Gap on this path"}
          </Badge>
        </div>
        {!evidenced && (
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted">
            {skill.why}
          </p>
        )}
      </div>
    </>
  );

  if (evidenced) {
    return (
      <li className="flex items-start gap-2 rounded-[var(--radius-control)] border border-line bg-surface-subtle px-2.5 py-2">
        {content}
      </li>
    );
  }

  return (
    <li className="rounded-[var(--radius-control)] border border-line bg-surface-subtle">
      <details className="group px-2.5 py-2">
        <summary className="flex cursor-pointer list-none items-start gap-2 marker:content-none [&::-webkit-details-marker]:hidden">
          <CircleDashed
            aria-hidden="true"
            className="mt-0.5 size-4 shrink-0 text-warning-visual"
          />
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm font-semibold leading-5 text-foreground">
                {skill.name}
              </p>
              <Badge className="shrink-0" tone="warning">
                Gap on this path
              </Badge>
            </div>
          </div>
        </summary>
        <div className="mt-2 border-t border-line pt-2 text-xs leading-5 text-muted">
          <p>
            <span className="font-semibold text-foreground">Why:</span>{" "}
            {skill.why}
          </p>
          <p className="mt-1">
            <span className="font-semibold text-foreground">First step:</span>{" "}
            {skill.howToStart}
          </p>
        </div>
      </details>
    </li>
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
    <Card className="p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[0.6875rem] font-bold uppercase tracking-[0.14em] text-primary">
            Promotion Readiness
          </p>
          <h3 className="mt-1 text-base font-semibold tracking-[-0.02em] sm:text-lg">
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
        className="mt-2 max-w-4xl text-xs font-semibold leading-5 text-muted"
        data-testid="promotion-readiness-disclaimer"
      >
        {disclaimer}
      </p>
      <p className="mt-1 text-xs text-muted">
        Generated {formattedDateTime(generatedAt)}
      </p>
      <Stepper
        className="mt-4"
        label="Promotion preparation path"
        steps={stepperSteps}
      />
      <details className="mt-4 rounded-[var(--radius-control)] border border-line bg-surface-subtle px-3 py-2">
        <summary className="cursor-pointer text-sm font-semibold text-foreground">
          View full preparation checklist ({checks.length})
        </summary>
        <div className="data-region table-scroll mt-3">
          <table className="min-w-full divide-y divide-line text-left text-sm">
            <caption className="sr-only">
              Promotion preparation checks, evidence state, and next action
            </caption>
            <thead className="bg-surface text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-3 py-2" scope="col">
                  Signal
                </th>
                <th className="px-3 py-2" scope="col">
                  State
                </th>
                <th className="px-3 py-2" scope="col">
                  Explanation
                </th>
                <th className="px-3 py-2" scope="col">
                  Evidence
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {checks.map((check) => (
                <tr key={check.code}>
                  <th className="px-3 py-2 font-bold" scope="row">
                    {check.label}
                  </th>
                  <td className="px-3 py-2">
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
                  <td className="min-w-48 px-3 py-2 text-muted">
                    {check.explanation}
                  </td>
                  <td className="px-3 py-2">
                    {check.evidenceCount === 0
                      ? "None linked"
                      : `${check.evidenceCount} eligible`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </Card>
  );
}

function CollapsibleSection({
  children,
  defaultOpen,
  summary,
}: {
  children: ReactNode;
  defaultOpen: boolean;
  summary: string;
}) {
  return (
    <details
      className="rounded-[var(--radius-card)] border border-line bg-surface"
      open={defaultOpen}
    >
      <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-foreground marker:content-none [&::-webkit-details-marker]:hidden">
        {summary}
      </summary>
      <div className="border-t border-line px-4 pb-4 pt-3">{children}</div>
    </details>
  );
}

function AchievementTimeline({
  achievements,
}: {
  achievements: CareerGrowthInsights["achievements"];
}) {
  if (achievements.length === 0) {
    return (
      <EmptyState
        description="Confirm supported achievements in the Evidence Vault to build this history."
        title="No eligible achievements yet"
      />
    );
  }

  return (
    <ol className="space-y-2">
      {achievements.map((item) => (
        <li
          className="rounded-[var(--radius-control)] border border-line bg-surface-subtle px-3 py-2.5"
          key={item.evidenceRevisionId}
        >
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="success">{humanize(item.strength)}</Badge>
            <span className="text-xs text-muted">
              {formattedDateTime(item.revisedAt)}
            </span>
          </div>
          <h4 className="mt-1 text-sm font-semibold">{item.title}</h4>
          <p className="mt-0.5 line-clamp-2 text-xs leading-5 text-muted">
            {item.statement}
          </p>
          <Link
            className="mt-1 inline-flex text-xs font-bold text-primary hover:underline"
            href={`/evidence/${item.evidenceId}`}
          >
            Review evidence
          </Link>
        </li>
      ))}
    </ol>
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

  if (skills.length === 0) {
    return (
      <EmptyState
        description="Add skills to your Career Profile and connect eligible evidence."
        title="No documented skills yet"
      />
    );
  }

  return (
    <div className="space-y-3">
      {categories.length > 0 && (
        <ul className="grid gap-2 sm:grid-cols-2">
          {categories.map(([category, counts]) => (
            <li key={category}>
              <Progress
                label={`${humanize(category)} · ${counts.evidenced}/${counts.total}`}
                value={Math.round((counts.evidenced / counts.total) * 100)}
              />
            </li>
          ))}
        </ul>
      )}
      <div className="data-region max-h-64 overflow-y-auto rounded-[var(--radius-control)] border border-line">
        <table className="min-w-full divide-y divide-line text-left text-sm">
          <caption className="sr-only">
            Documented skills and their eligible evidence coverage
          </caption>
          <thead className="sticky top-0 bg-surface-subtle text-xs uppercase tracking-wide text-muted">
            <tr>
              <th className="px-3 py-2" scope="col">
                Skill
              </th>
              <th className="px-3 py-2" scope="col">
                Evidence
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {skills.map((skill) => (
              <tr key={skill.skillId}>
                <th className="px-3 py-2 font-semibold" scope="row">
                  <span className="block">{skill.name}</span>
                  <span className="text-xs font-normal text-muted">
                    {skill.category ? humanize(skill.category) : "Uncategorized"}
                  </span>
                </th>
                <td className="px-3 py-2">
                  {skill.evidenceCount === 0 ? (
                    <Badge tone="warning">Not demonstrated</Badge>
                  ) : (
                    <Badge tone="success">
                      {skill.evidenceCount} eligible
                    </Badge>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AnnualRefreshCard({
  items,
}: {
  items: CareerGrowthInsights["annualResumeRefreshes"];
}) {
  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold tracking-[-0.02em]">
        Annual resume refresh workflow
      </h3>
      <ul className="mt-3 grid gap-2 sm:grid-cols-2">
        {items.map((item) => (
          <li
            className="rounded-[var(--radius-control)] border border-line bg-surface-subtle px-3 py-2.5"
            key={item.id}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm font-semibold">{item.title}</span>
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
            <p className="mt-1 text-xs text-muted">
              Target {formattedDate(item.targetDate)} ·{" "}
              {item.evidenceLinks.length} evidence link(s)
            </p>
          </li>
        ))}
      </ul>
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
