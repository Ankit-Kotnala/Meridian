"use client";

import {
  ArrowRight,
  CheckCircle2,
  RefreshCcw,
  Sparkles,
  Target,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

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

        <RoadmapConnectedPath
          expandedSkill={openSkill}
          onToggleDetails={(name) =>
            setOpenSkill((current) => (current === name ? undefined : name))
          }
          onToggleSkill={toggle}
          selected={selected}
          stages={roadmap.stages}
          stageTotal={summary.stages}
        />

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
      <p className="text-[0.625rem] font-bold uppercase tracking-[0.1em] text-muted">
        {label}
      </p>
      <p className="text-lg font-semibold tabular-nums leading-tight text-foreground">
        {value}
      </p>
    </div>
  );
}

type RoadmapPathNode = {
  isFirstInStage: boolean;
  skill: RoadmapSkill;
  stageIndex: number;
  stageName: string;
};

function buildRoadmapPath(stages: RoleRoadmap["stages"]): RoadmapPathNode[] {
  return stages.flatMap((stage, stageIndex) =>
    stage.skills.map((skill, skillIndex) => ({
      isFirstInStage: skillIndex === 0,
      skill,
      stageIndex,
      stageName: stage.stage,
    })),
  );
}

function RoadmapConnectedPath({
  expandedSkill,
  onToggleDetails,
  onToggleSkill,
  selected,
  stages,
  stageTotal,
}: {
  expandedSkill: string | undefined;
  onToggleDetails: (name: string) => void;
  onToggleSkill: (name: string) => void;
  selected: ReadonlySet<string>;
  stages: RoleRoadmap["stages"];
  stageTotal: number;
}) {
  const nodes = buildRoadmapPath(stages);
  const expandedNode = nodes.find((node) => node.skill.name === expandedSkill);

  return (
    <div
      className="relative overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface-subtle/60 p-4 sm:p-6"
      role="list"
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-35 [background-image:radial-gradient(var(--border-strong)_1px,transparent_1px)] [background-size:22px_22px]"
      />
      <div className="relative mx-auto max-w-5xl">
        <p className="mb-6 text-center text-xs font-semibold uppercase tracking-[0.14em] text-muted">
          Follow the connected path — each node is a skill stop on your journey
        </p>

        <div className="mx-auto flex max-w-md flex-col items-center gap-0" role="list">
          {nodes.map((node, nodeIndex) => {
            const accent = stageAccent(node.stageIndex);
            const isLast = nodeIndex === nodes.length - 1;
            return (
              <div
                className="flex flex-col items-center"
                key={node.skill.name}
                role="listitem"
              >
                <RoadmapCircularNode
                  accent={accent}
                  expanded={expandedSkill === node.skill.name}
                  isFirstInStage={node.isFirstInStage}
                  onToggleDetails={() => onToggleDetails(node.skill.name)}
                  onToggleSkill={() => onToggleSkill(node.skill.name)}
                  selected={selected.has(node.skill.name)}
                  stageIndex={node.stageIndex}
                  stageName={node.stageName}
                  stageTotal={stageTotal}
                  skill={node.skill}
                />
                {!isLast && <RoadmapPathConnector accent={accent} />}
              </div>
            );
          })}
        </div>

        {expandedNode && (
          <RoadmapSkillDetail
            accent={stageAccent(expandedNode.stageIndex)}
            onClose={() => onToggleDetails(expandedNode.skill.name)}
            onToggle={() => onToggleSkill(expandedNode.skill.name)}
            selected={selected.has(expandedNode.skill.name)}
            skill={expandedNode.skill}
          />
        )}
      </div>
    </div>
  );
}

function RoadmapPathConnector({ accent }: { accent: StageAccent }) {
  return (
    <div aria-hidden="true" className="flex flex-col items-center py-1">
      <span className={cn("h-10 w-0.5", accent.bar, "opacity-50")} />
      <span
        className={cn(
          "flex size-5 shrink-0 items-center justify-center rounded-full border-2 bg-surface",
          accent.node,
        )}
      >
        <ArrowRight
          className="size-3 rotate-90 text-muted"
          aria-hidden="true"
        />
      </span>
      <span className={cn("h-10 w-0.5", accent.bar, "opacity-50")} />
    </div>
  );
}

function RoadmapCircularNode({
  accent,
  expanded,
  isFirstInStage,
  onToggleDetails,
  onToggleSkill,
  selected,
  stageIndex,
  stageName,
  stageTotal,
  skill,
}: {
  accent: StageAccent;
  expanded: boolean;
  isFirstInStage: boolean;
  onToggleDetails: () => void;
  onToggleSkill: () => void;
  selected: boolean;
  stageIndex: number;
  stageName: string;
  stageTotal: number;
  skill: RoadmapSkill;
}) {
  const demonstrated = skill.alreadyDemonstrated;

  return (
    <div className="relative flex w-[9.5rem] flex-col items-center px-1 pt-10 sm:w-[10.5rem]">
      {isFirstInStage && (
        <a
          className={cn(
            "absolute top-0 left-1/2 z-10 -translate-x-1/2 rounded-full px-2.5 py-0.5 text-[0.625rem] font-bold uppercase tracking-[0.08em] whitespace-nowrap shadow-sm",
            accent.chip,
          )}
          href={`#roadmap-stage-${stageIndex}`}
          id={`roadmap-stage-${stageIndex}`}
        >
          <span className="sr-only">Stage {stageIndex + 1} of {stageTotal}: </span>
          {stageName}
        </a>
      )}

      <div className="relative">
        <button
          aria-expanded={expanded}
          className="group flex w-full flex-col items-center"
          onClick={onToggleDetails}
          type="button"
        >
          <span
            className={cn(
              "relative flex size-[4.5rem] items-center justify-center rounded-full border-[3px] bg-surface shadow-[var(--shadow-sm)] transition-[border-color,box-shadow,transform] duration-200 motion-reduce:transition-none sm:size-20",
              accent.node,
              selected && cn("border-primary shadow-md ring-4 ring-offset-2", accent.ring),
              demonstrated && !selected && "opacity-95",
              expanded && "scale-105",
            )}
          >
            {demonstrated ? (
              <CheckCircle2
                aria-hidden="true"
                className="size-7 text-success sm:size-8"
              />
            ) : (
              <Target
                aria-hidden="true"
                className="size-7 text-warning sm:size-8"
              />
            )}
          </span>
          <span className="mt-3 line-clamp-2 min-w-0 text-center text-xs font-semibold leading-snug tracking-[-0.01em] text-foreground group-hover:text-primary sm:text-sm">
            {skill.name}
          </span>
        </button>
        <label
          className="absolute -top-1 -right-1 flex size-7 items-center justify-center rounded-full border border-line bg-surface shadow-sm"
        >
          <input
            aria-label={`Include ${skill.name} in your development plan`}
            checked={selected}
            className="size-4 accent-primary"
            onChange={onToggleSkill}
            type="checkbox"
          />
        </label>
      </div>

      <Badge
        className="mt-2 max-w-full truncate"
        tone={demonstrated ? "success" : "warning"}
      >
        {demonstrated ? "Evidence found" : "Suggested focus"}
      </Badge>
    </div>
  );
}

function RoadmapSkillDetail({
  accent,
  onClose,
  onToggle,
  selected,
  skill,
}: {
  accent: StageAccent;
  onClose: () => void;
  onToggle: () => void;
  selected: boolean;
  skill: RoadmapSkill;
}) {
  const demonstrated = skill.alreadyDemonstrated;

  return (
    <div
      className={cn(
        "mt-8 rounded-[var(--radius-card)] border-2 bg-surface p-4 shadow-[var(--shadow-md)] sm:p-5",
        accent.node,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-muted">
            Skill detail
          </p>
          <h4 className="mt-1 text-base font-semibold tracking-[-0.02em] text-foreground sm:text-lg">
            {skill.name}
          </h4>
          <Badge className="mt-2" tone={demonstrated ? "success" : "warning"}>
            {demonstrated ? "Evidence found" : "Suggested focus"}
          </Badge>
        </div>
        <label className="flex shrink-0 items-center gap-2 text-sm text-muted">
          <input
            aria-label={`Include ${skill.name} in your development plan`}
            checked={selected}
            className="size-4 accent-primary"
            onChange={onToggle}
            type="checkbox"
          />
          Include in plan
        </label>
      </div>
      <p className="mt-4 text-sm leading-6 text-muted">{skill.why}</p>
      {skill.howToStart ? (
        <p className="mt-3 rounded-md border border-line bg-surface-subtle px-3 py-2 text-xs leading-5 text-muted-strong sm:text-sm">
          <strong className="font-semibold text-foreground">Start here:</strong>{" "}
          {skill.howToStart}
        </p>
      ) : null}
      <div className="mt-4 flex justify-end">
        <Button className="min-h-8 px-3 text-xs" onClick={onClose} variant="ghost">
          Close detail
        </Button>
      </div>
    </div>
  );
}
