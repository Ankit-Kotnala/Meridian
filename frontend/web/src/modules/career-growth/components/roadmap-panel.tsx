"use client";

import {
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  RefreshCcw,
  Sparkles,
  Target,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useId, useMemo, useState } from "react";

import {
  Alert,
  Badge,
  Button,
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  buttonStyles,
  cn,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import { confirmRoleRoadmap, getRoleRoadmap } from "../api/career-growth-api";
import type { RoadmapSkill, RoleRoadmap } from "../api/types";

const STAGE_ACCENTS = [
  {
    bar: "bg-primary",
    chip: "bg-primary-soft text-primary",
    node: "border-primary/35 hover:border-primary/60",
    ring: "ring-primary/25",
  },
  {
    bar: "bg-success",
    chip: "bg-success-soft text-success",
    node: "border-success/35 hover:border-success/60",
    ring: "ring-success/25",
  },
  {
    bar: "bg-warning-visual",
    chip: "bg-warning-soft text-warning",
    node: "border-warning-visual/40 hover:border-warning-visual/70",
    ring: "ring-warning-visual/25",
  },
] as const;

type StageAccent = (typeof STAGE_ACCENTS)[number];

function stageAccent(stageIndex: number): StageAccent {
  const accent = STAGE_ACCENTS[stageIndex % STAGE_ACCENTS.length];
  return accent ?? STAGE_ACCENTS[0];
}

/**
 * "Your roadmap": resolves the owner's target role, shows the curated skill
 * path for it, and marks skills they already have evidence for so they can
 * opt out of what they already know before confirming.
 */
export function RoadmapPanel({ onConfirmed }: { onConfirmed?: () => void }) {
  const [roadmap, setRoadmap] = useState<RoleRoadmap | null>();
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [openSkill, setOpenSkill] = useState<string>();
  const [failure, setFailure] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setFailure(undefined);
    try {
      const value = await getRoleRoadmap();
      setRoadmap(value);
      setOpenSkill(undefined);
      if (value) {
        const defaults = new Set<string>();
        for (const stage of value.stages) {
          for (const skill of stage.skills) {
            if (!skill.alreadyDemonstrated) defaults.add(skill.name);
          }
        }
        setSelected(defaults);
      }
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "Your roadmap could not be loaded."),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  function toggle(name: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  async function confirm() {
    if (!roadmap) return;
    setBusy(true);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const result = await confirmRoleRoadmap({
        includedSkillNames: Array.from(selected),
        roleTitle: roadmap.roleTitle,
      });
      setSuccess(
        result.created.length === 0
          ? "No new development items — everything selected was already tracked."
          : `${result.created.length} development ${result.created.length === 1 ? "item" : "items"} added to your plan below.`,
      );
      onConfirmed?.();
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "Your roadmap could not be confirmed."),
      );
    } finally {
      setBusy(false);
    }
  }

  const summary = useMemo(() => {
    const skills = roadmap?.stages.flatMap((stage) => stage.skills) ?? [];
    return {
      demonstrated: skills.filter((skill) => skill.alreadyDemonstrated).length,
      focus: skills.filter((skill) => !skill.alreadyDemonstrated).length,
      stages: roadmap?.stages.length ?? 0,
      total: skills.length,
    };
  }, [roadmap]);

  if (loading) {
    return (
      <div aria-label="Loading personalized roadmap" role="status">
        <LoadingSkeleton className="min-h-72 p-4" />
      </div>
    );
  }

  if (roadmap === undefined) {
    return (
      <ErrorState
        description={failure ?? "Refresh and try again."}
        onRetry={() => void load()}
        title="Personalized roadmap unavailable"
      />
    );
  }

  if (roadmap === null) {
    return (
      <div className="surface-card rounded-[var(--radius-card)] p-5 sm:p-6">
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
          description="We could not match a roadmap to the role in your latest resume or Career Record. Review the role title or add an experience, and we will personalize the next roadmap from eligible profile evidence."
          title="We could not identify your role yet"
        />
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface shadow-[var(--shadow-sm)]">
      <div className="relative border-b border-line bg-gradient-to-br from-primary-soft/80 via-surface to-surface px-5 py-6 sm:px-6 sm:py-7">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 opacity-[0.45] [background-image:radial-gradient(var(--border-strong)_1px,transparent_1px)] [background-size:18px_18px]"
        />
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <Badge tone="primary">Personalized at runtime</Badge>
            <h3 className="mt-3 text-2xl font-bold tracking-[-0.03em] text-foreground sm:text-[1.75rem]">
              Your path to {roadmap.roleTitle}
            </h3>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
              Follow the staged map from foundations to advanced topics. Open a
              skill to see why it matters and a concrete first step.
            </p>
            <nav aria-label="Roadmap stages" className="mt-4">
              <ol className="flex flex-wrap items-center gap-2">
                {roadmap.stages.map((stage, stageIndex) => {
                  const accent = stageAccent(stageIndex);
                  return (
                    <li className="flex items-center gap-2" key={stage.stage}>
                      {stageIndex > 0 && (
                        <ArrowRight
                          aria-hidden="true"
                          className="size-3.5 shrink-0 text-muted"
                        />
                      )}
                      <a
                        className={cn(
                          "rounded-full px-3 py-1 text-xs font-semibold tracking-[-0.01em] underline-offset-4 transition-colors hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
                          accent.chip,
                        )}
                        href={`#roadmap-stage-${stageIndex}`}
                      >
                        {stage.stage}
                      </a>
                    </li>
                  );
                })}
              </ol>
            </nav>
          </div>
          <dl className="flex flex-wrap gap-2 lg:justify-end">
            <StatChip label="Skills mapped" value={summary.total} />
            <StatChip label="Evidence found" value={summary.demonstrated} />
            <StatChip label="Focus areas" value={summary.focus} />
          </dl>
        </div>
      </div>

      <div className="p-5 sm:p-6">
        {(failure || success) && (
          <div className="mb-5 space-y-3">
            {failure && (
              <Alert title="Roadmap selection not saved" tone="danger">
                {failure}
              </Alert>
            )}
            {success && (
              <Alert title="Development plan updated" tone="success">
                <p role="status">{success}</p>
              </Alert>
            )}
          </div>
        )}

        <div
          className="relative overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface-subtle/60 p-4 sm:p-5"
          role="list"
        >
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 opacity-30 [background-image:radial-gradient(var(--border-strong)_1px,transparent_1px)] [background-size:20px_20px]"
          />
          <div className="relative flex flex-col gap-6 lg:flex-row lg:items-stretch lg:gap-4">
            {roadmap.stages.map((stage, stageIndex) => (
              <RoadmapStageLane
                accent={stageAccent(stageIndex)}
                expandedSkill={openSkill}
                key={stage.stage}
                onToggleDetails={(name) =>
                  setOpenSkill((current) =>
                    current === name ? undefined : name,
                  )
                }
                onToggleSkill={toggle}
                selected={selected}
                stage={stage}
                stageIndex={stageIndex}
                stageTotal={summary.stages}
              />
            ))}
          </div>
        </div>

        <div className="mt-5 flex flex-col gap-3 border-t border-line pt-5 sm:flex-row sm:items-center sm:justify-between">
          <p className="flex items-start gap-2 text-sm text-muted">
            <Sparkles
              aria-hidden="true"
              className="mt-0.5 size-4 shrink-0 text-primary"
            />
            {selected.size} {selected.size === 1 ? "skill" : "skills"} selected
            for your development plan. Skills with evidence are unchecked by
            default.
          </p>
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <Button disabled={busy} onClick={() => void load()} variant="ghost">
              <RefreshCcw aria-hidden="true" className="size-4" />
              Recheck evidence
            </Button>
            <Button
              disabled={selected.size === 0}
              loading={busy}
              onClick={() => void confirm()}
            >
              Add selected to growth plan
              <ArrowRight aria-hidden="true" className="size-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatChip({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-full border border-line bg-surface px-3 py-1.5 shadow-[var(--shadow-sm)]">
      <dt className="text-[0.625rem] font-bold uppercase tracking-[0.1em] text-muted">
        {label}
      </dt>
      <dd className="text-lg font-semibold tabular-nums leading-tight text-foreground">
        {value}
      </dd>
    </div>
  );
}

function RoadmapStageLane({
  accent,
  expandedSkill,
  onToggleDetails,
  onToggleSkill,
  selected,
  stage,
  stageIndex,
  stageTotal,
}: {
  accent: StageAccent;
  expandedSkill: string | undefined;
  onToggleDetails: (name: string) => void;
  onToggleSkill: (name: string) => void;
  selected: ReadonlySet<string>;
  stage: RoleRoadmap["stages"][number];
  stageIndex: number;
  stageTotal: number;
}) {
  return (
  <section
    aria-labelledby={`roadmap-stage-${stageIndex}`}
    className="relative flex min-w-0 flex-1 flex-col"
    role="listitem"
  >
    {stageIndex < stageTotal - 1 && (
      <div
        aria-hidden="true"
        className="absolute top-10 right-0 hidden h-px w-4 translate-x-full bg-gradient-to-r from-border-strong to-transparent lg:block"
      />
    )}
    <div className="overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface shadow-[var(--shadow-sm)]">
      <div className={cn("h-1.5 w-full", accent.bar)} />
      <header className="border-b border-line px-4 py-3">
        <p className="text-[0.625rem] font-bold uppercase tracking-[0.14em] text-muted">
          Stage {stageIndex + 1} of {stageTotal}
        </p>
        <h4
          className="mt-1 text-base font-semibold tracking-[-0.02em] text-foreground"
          id={`roadmap-stage-${stageIndex}`}
        >
          {stage.stage}
        </h4>
      </header>
      <ol className="space-y-2 p-3">
        {stage.skills.map((skill, skillIndex) => (
          <RoadmapSkillNode
            accent={accent}
            expanded={expandedSkill === skill.name}
            key={skill.name}
            onToggle={() => onToggleSkill(skill.name)}
            onToggleDetails={() => onToggleDetails(skill.name)}
            selected={selected.has(skill.name)}
            showConnector={skillIndex < stage.skills.length - 1}
            skill={skill}
          />
        ))}
      </ol>
    </div>
  </section>
  );
}

function canHoverRevealDetails() {
  return Boolean(
    window.matchMedia?.("(hover: hover) and (pointer: fine)").matches,
  );
}

function RoadmapSkillNode({
  accent,
  expanded,
  onToggle,
  onToggleDetails,
  selected,
  showConnector,
  skill,
}: {
  accent: StageAccent;
  expanded: boolean;
  onToggle: () => void;
  onToggleDetails: () => void;
  selected: boolean;
  showConnector: boolean;
  skill: RoadmapSkill;
}) {
  const detailId = useId();
  const [hovered, setHovered] = useState(false);
  const showDetails = expanded || hovered;
  const demonstrated = skill.alreadyDemonstrated;

  return (
    <li
      className="relative"
      onMouseEnter={() => {
        if (canHoverRevealDetails()) setHovered(true);
      }}
      onMouseLeave={() => setHovered(false)}
    >
      {showConnector && (
        <span
          aria-hidden="true"
          className="absolute left-5 top-full h-2 w-px bg-border-strong"
        />
      )}
      <div
        className={cn(
          "relative rounded-[var(--radius-control)] border-2 bg-surface transition-[border-color,box-shadow,transform] duration-200 motion-reduce:transition-none",
          accent.node,
          selected && cn("border-primary shadow-md ring-4", accent.ring),
          !selected && demonstrated && "opacity-90",
        )}
      >
        <div className="flex items-start gap-2 p-3">
          <span
            aria-hidden="true"
            className={cn(
              "mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full",
              demonstrated ? "bg-success-soft text-success" : "bg-warning-soft text-warning",
            )}
          >
            {demonstrated ? (
              <CheckCircle2 className="size-4" />
            ) : (
              <Target className="size-4" />
            )}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <button
                aria-controls={detailId}
                aria-expanded={showDetails}
                className="inline-flex min-w-0 items-start gap-1 rounded-[var(--radius-small)] text-left text-sm font-semibold tracking-[-0.01em] text-foreground hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                onClick={onToggleDetails}
                type="button"
              >
                <span className="min-w-0">{skill.name}</span>
                <ChevronDown
                  aria-hidden="true"
                  className={cn(
                    "mt-0.5 size-4 shrink-0 text-muted transition-transform duration-200 motion-reduce:transition-none",
                    showDetails && "rotate-180",
                  )}
                />
              </button>
              <input
                aria-describedby={showDetails ? detailId : undefined}
                aria-label={`Include ${skill.name} in your development plan`}
                checked={selected}
                className="mt-0.5 size-4 shrink-0 accent-primary"
                onChange={onToggle}
                type="checkbox"
              />
            </div>
            <Badge
              className="mt-2"
              tone={demonstrated ? "success" : "warning"}
            >
              {demonstrated ? "Evidence found" : "Suggested focus"}
            </Badge>
            <div
              className={cn(
                "grid transition-[grid-template-rows] duration-200 motion-reduce:transition-none",
                showDetails ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
              )}
              hidden={!showDetails}
              id={detailId}
            >
              <div className="min-h-0 overflow-hidden">
                <p className="mt-3 text-sm leading-6 text-muted">{skill.why}</p>
                {skill.howToStart ? (
                  <p className="mt-3 rounded-md border border-line bg-surface-subtle px-3 py-2 text-xs leading-5 text-muted-strong">
                    <strong className="font-semibold text-foreground">
                      Start here:
                    </strong>{" "}
                    {skill.howToStart}
                  </p>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      </div>
    </li>
  );
}
