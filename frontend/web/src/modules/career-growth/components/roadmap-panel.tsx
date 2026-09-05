"use client";

import {
  ArrowRight,
  CheckCircle2,
  RefreshCcw,
  Sparkles,
  Star,
} from "lucide-react";
import Link from "next/link";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FocusEvent,
} from "react";

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

const STAGE_THEMES = [
  {
    chip: "bg-primary-soft text-primary border-primary/15",
    dot: "bg-primary text-white",
    dotRing: "ring-primary/25",
    stageBar: "border-primary/20 bg-primary-soft/80",
    card: "border-primary/12 hover:border-primary/30",
    cardHover:
      "hover:shadow-[0_12px_32px_color-mix(in_srgb,var(--primary)_14%,transparent)]",
    accent: "text-primary",
    navActive: "border-primary bg-primary-soft text-primary",
    navIdle:
      "border-line bg-surface text-muted-strong hover:border-primary/25 hover:text-foreground",
  },
  {
    chip: "bg-success-soft text-success border-success/15",
    dot: "bg-success text-white",
    dotRing: "ring-success/25",
    stageBar: "border-success/20 bg-success-soft/80",
    card: "border-success/12 hover:border-success/30",
    cardHover:
      "hover:shadow-[0_12px_32px_color-mix(in_srgb,var(--success)_14%,transparent)]",
    accent: "text-success",
    navActive: "border-success bg-success-soft text-success",
    navIdle:
      "border-line bg-surface text-muted-strong hover:border-success/25 hover:text-foreground",
  },
  {
    chip: "bg-warning-soft text-warning border-warning-visual/15",
    dot: "bg-warning-visual text-white",
    dotRing: "ring-warning-visual/25",
    stageBar: "border-warning-visual/20 bg-warning-soft/80",
    card: "border-warning-visual/12 hover:border-warning-visual/35",
    cardHover:
      "hover:shadow-[0_12px_32px_color-mix(in_srgb,var(--warning-visual)_14%,transparent)]",
    accent: "text-warning",
    navActive: "border-warning-visual bg-warning-soft text-warning",
    navIdle:
      "border-line bg-surface text-muted-strong hover:border-warning-visual/25 hover:text-foreground",
  },
] as const;

type StageTheme = (typeof STAGE_THEMES)[number];

function stageTheme(stageIndex: number): StageTheme {
  const theme = STAGE_THEMES[stageIndex % STAGE_THEMES.length];
  return theme ?? STAGE_THEMES[0];
}

function usePrefersHover() {
  const [prefersHover, setPrefersHover] = useState(() => {
    if (typeof window.matchMedia !== "function") return false;
    return window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  });

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(hover: hover) and (pointer: fine)");
    const sync = () => setPrefersHover(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  return prefersHover;
}

type RoadmapPathNode = {
  globalIndex: number;
  isFirstInStage: boolean;
  skill: RoadmapSkill;
  stageIndex: number;
  stageName: string;
};

function buildRoadmapPath(stages: RoleRoadmap["stages"]): RoadmapPathNode[] {
  let globalIndex = 0;
  return stages.flatMap((stage, stageIndex) =>
    stage.skills.map((skill, skillIndex) => {
      const node: RoadmapPathNode = {
        globalIndex: globalIndex++,
        isFirstInStage: skillIndex === 0,
        skill,
        stageIndex,
        stageName: stage.stage,
      };
      return node;
    }),
  );
}

function findNextFocusSkill(nodes: RoadmapPathNode[]): RoadmapPathNode | undefined {
  return nodes.find((node) => !node.skill.alreadyDemonstrated);
}

const EVIDENCE_COVERAGE_DISCLAIMER =
  "Evidence coverage is an internal Rezumi measure from your Career Record — not an employer or ATS score.";

/**
 * "Your roadmap": resolves the owner's target role, shows the curated skill
 * path for it, and marks skills they already have evidence for so they can
 * opt out of what they already know before confirming.
 */
export function RoadmapPanel({
  mode = "growth",
  onConfirmed,
  onPracticeSkill,
}: {
  mode?: "growth" | "interview";
  onConfirmed?: () => void;
  onPracticeSkill?: (skill: RoadmapSkill) => void;
}) {
  const [roadmap, setRoadmap] = useState<RoleRoadmap | null>();
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
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
    const demonstrated = skills.filter((skill) => skill.alreadyDemonstrated).length;
    return {
      demonstrated,
      focus: skills.filter((skill) => !skill.alreadyDemonstrated).length,
      progress:
        skills.length === 0
          ? 0
          : Math.round((demonstrated / skills.length) * 100),
      stages: roadmap?.stages.length ?? 0,
      total: skills.length,
    };
  }, [roadmap]);

  if (loading) {
    return (
      <div aria-label="Loading personalized roadmap" role="status">
        <LoadingSkeleton className="min-h-[28rem] rounded-[var(--radius-card)]" />
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

  if (mode === "interview") {
    return (
      <div className="space-y-5">
        <InterviewPathSummary
          demonstrated={summary.demonstrated}
          progress={summary.progress}
          roleTitle={roadmap.roleTitle}
          stages={roadmap.stages}
          total={summary.total}
        />

        {(failure || success) && (
          <div className="space-y-3">
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

        <InterviewJourney
          onToggleSkill={toggle}
          selected={selected}
          stages={roadmap.stages}
          stageTotal={summary.stages}
          {...(onPracticeSkill ? { onPracticeSkill } : {})}
        />
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface shadow-[var(--shadow-md)]">
      <RoadmapHero
        demonstrated={summary.demonstrated}
        focus={summary.focus}
        progress={summary.progress}
        roleTitle={roadmap.roleTitle}
        stages={roadmap.stages}
        total={summary.total}
      />

      <div className="border-t border-line bg-background/60 p-5 sm:p-8">
        {(failure || success) && (
          <div className="mb-6 space-y-3">
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

        <GrowthJourney
          onToggleSkill={toggle}
          selected={selected}
          stages={roadmap.stages}
          stageTotal={summary.stages}
        />

        <div className="mt-8 flex flex-col gap-4 border-t border-line pt-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="flex items-start gap-2 text-sm leading-6 text-muted">
            <Sparkles
              aria-hidden="true"
              className="mt-0.5 size-4 shrink-0 text-primary"
            />
            <span>
              <strong className="font-semibold text-foreground">
                {selected.size}
              </strong>{" "}
              {selected.size === 1 ? "skill" : "skills"} queued for your plan.
              Evidence-backed skills stay unchecked by default.
            </span>
          </p>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:shrink-0">
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

function InterviewPathSummary({
  demonstrated,
  progress,
  roleTitle,
  stages,
  total,
}: {
  demonstrated: number;
  progress: number;
  roleTitle: string;
  stages: RoleRoadmap["stages"];
  total: number;
}) {
  return (
    <section
      aria-labelledby="interview-path-heading"
      className="rounded-[var(--radius-card)] border border-line bg-surface px-5 py-5 sm:px-6 sm:py-6"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h3
            className="font-display text-xl font-semibold tracking-[-0.02em] text-foreground sm:text-[1.375rem]"
            id="interview-path-heading"
          >
            Path to {roleTitle}
          </h3>
          <p className="mt-1 text-sm text-muted">
            <span className="font-semibold tabular-nums text-foreground">
              {demonstrated} of {total}
            </span>{" "}
            {total === 1 ? "skill" : "skills"} evidenced
          </p>
        </div>
        <nav aria-label="Roadmap stages">
          <ol className="flex flex-wrap gap-2 sm:justify-end">
            {stages.map((stage, stageIndex) => {
              const theme = stageTheme(stageIndex);
              const stageDemonstrated = stage.skills.filter(
                (skill) => skill.alreadyDemonstrated,
              ).length;
              return (
                <li key={stage.stage}>
                  <a
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
                      theme.chip,
                    )}
                    href={`#roadmap-stage-${stageIndex}`}
                  >
                    {stage.stage}
                    <span className="tabular-nums opacity-80">
                      {stageDemonstrated}/{stage.skills.length}
                    </span>
                  </a>
                </li>
              );
            })}
          </ol>
        </nav>
      </div>

      <div className="mt-5">
        <div className="flex items-center justify-between gap-3 text-xs font-semibold text-muted">
          <span>Evidence coverage</span>
          <span className="tabular-nums text-foreground">{progress}%</span>
        </div>
        <div
          aria-hidden="true"
          className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--score-track)]"
        >
          <div
            className="h-full rounded-full bg-primary transition-[width] duration-500 motion-reduce:transition-none"
            style={{ width: `${progress}%` }}
          />
        </div>
        <p className="mt-2 text-xs leading-5 text-muted">
          {EVIDENCE_COVERAGE_DISCLAIMER}
        </p>
      </div>
    </section>
  );
}

function InterviewJourney({
  onPracticeSkill,
  onToggleSkill,
  selected,
  stages,
  stageTotal,
}: {
  onPracticeSkill?: (skill: RoadmapSkill) => void;
  onToggleSkill: (name: string) => void;
  selected: ReadonlySet<string>;
  stages: RoleRoadmap["stages"];
  stageTotal: number;
}) {
  const nodes = buildRoadmapPath(stages);
  const nextFocus = findNextFocusSkill(nodes);
  const [activeSkillName, setActiveSkillName] = useState(
    () => nextFocus?.skill.name ?? nodes[0]?.skill.name ?? "",
  );

  const activeNode =
    nodes.find((node) => node.skill.name === activeSkillName) ?? nodes[0];

  function selectSkill(name: string) {
    setActiveSkillName(name);
  }

  function jumpToSkillOnMap(globalIndex: number) {
    const target = document.getElementById(`roadmap-skill-${globalIndex}`);
    target?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function openSkillDetail(name: string) {
    selectSkill(name);
    queueMicrotask(() => {
      document
        .getElementById("interview-skill-detail")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  return (
    <div className="space-y-5">
      <div className="overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface">
        <div className="overflow-x-auto">
          <div
            className="min-w-[52rem]"
            style={{
              display: "grid",
              gridTemplateColumns: `repeat(${Math.max(nodes.length, 1)}, minmax(0, 1fr))`,
            }}
          >
            {stages.map((stage, stageIndex) => {
              const theme = stageTheme(stageIndex);
              const count = stage.skills.length;
              return (
                <div
                  className={cn(
                    "border-b border-line px-3 py-2.5 text-center",
                    theme.stageBar,
                  )}
                  id={`roadmap-stage-${stageIndex}`}
                  key={stage.stage}
                  style={{ gridColumn: `span ${count}` }}
                >
                  <p className="text-[0.625rem] font-bold uppercase tracking-[0.14em] text-muted">
                    <span className="sr-only">
                      Stage {stageIndex + 1} of {stageTotal}:{" "}
                    </span>
                    {stage.stage}
                    <span className="ml-1 font-semibold tracking-normal text-muted">
                      ({count} {count === 1 ? "skill" : "skills"})
                    </span>
                  </p>
                </div>
              );
            })}

            {nodes.map((node, index) => {
              const isActive = activeNode?.skill.name === node.skill.name;
              const demonstrated = node.skill.alreadyDemonstrated;
              return (
                <div
                  className="relative flex h-16 items-center justify-center"
                  key={`${node.skill.name}-marker`}
                >
                  {index > 0 ? (
                    <span
                      aria-hidden="true"
                      className="absolute inset-y-0 left-0 right-1/2 flex items-center pr-4"
                    >
                      <span className="h-px w-full bg-line-strong" />
                    </span>
                  ) : null}
                  {index < nodes.length - 1 ? (
                    <span
                      aria-hidden="true"
                      className="absolute inset-y-0 left-1/2 right-0 flex items-center pl-4"
                    >
                      <span className="h-px flex-1 bg-line-strong" />
                      <ArrowRight className="-mr-1.5 size-3.5 shrink-0 text-muted" />
                    </span>
                  ) : null}
                  <span
                    className={cn(
                      "relative z-10 flex size-8 items-center justify-center rounded-full border-2 text-xs font-bold tabular-nums",
                      demonstrated
                        ? "border-success bg-success text-white"
                        : isActive
                          ? "border-primary bg-primary text-white"
                          : "border-foreground/80 bg-surface text-foreground",
                    )}
                  >
                    {demonstrated ? (
                      <CheckCircle2 aria-hidden="true" className="size-4" />
                    ) : (
                      node.globalIndex + 1
                    )}
                  </span>
                </div>
              );
            })}

            {nodes.map((node) => (
              <div className="px-2 pb-4 pt-1" key={`${node.skill.name}-card`}>
                <InterviewSkillCard
                  active={activeNode?.skill.name === node.skill.name}
                  onOpen={() => openSkillDetail(node.skill.name)}
                  onSelect={() => selectSkill(node.skill.name)}
                  onToggleSkill={() => onToggleSkill(node.skill.name)}
                  selected={selected.has(node.skill.name)}
                  skill={node.skill}
                  step={node.globalIndex + 1}
                />
              </div>
            ))}
          </div>
        </div>
      </div>

      {activeNode ? (
        <InterviewSkillDetail
          isPriorityFocus={nextFocus?.skill.name === activeNode.skill.name}
          node={activeNode}
          onPractice={() => onPracticeSkill?.(activeNode.skill)}
          onShowOnMap={() => jumpToSkillOnMap(activeNode.globalIndex)}
          showPracticeAction={Boolean(onPracticeSkill)}
          skillTotal={nodes.length}
        />
      ) : null}
    </div>
  );
}

function InterviewSkillCard({
  active,
  onOpen,
  onSelect,
  onToggleSkill,
  selected,
  skill,
  step,
}: {
  active: boolean;
  onOpen: () => void;
  onSelect: () => void;
  onToggleSkill: () => void;
  selected: boolean;
  skill: RoadmapSkill;
  step: number;
}) {
  const demonstrated = skill.alreadyDemonstrated;

  return (
    <div
      className={cn(
        "flex h-full flex-col rounded-[var(--radius-card)] border bg-surface p-3.5 transition-[border-color,box-shadow] duration-200 motion-reduce:transition-none",
        active
          ? "border-primary shadow-[0_0_0_1px_var(--primary)]"
          : "border-line hover:border-line-strong",
      )}
      data-roadmap-node=""
      id={`roadmap-skill-${step - 1}`}
    >
      <div className="flex items-start gap-2">
        <input
          aria-label={`Include ${skill.name} in your development plan`}
          checked={selected}
          className="mt-0.5 size-4 shrink-0 accent-primary"
          onChange={onToggleSkill}
          type="checkbox"
        />
        <button
          className="min-w-0 flex-1 text-left"
          onClick={onSelect}
          type="button"
        >
          <h4 className="text-sm font-semibold leading-snug tracking-[-0.02em] text-foreground">
            {skill.name}
          </h4>
        </button>
      </div>
      <button
        className="mt-3 flex flex-wrap gap-1.5 text-left"
        onClick={onSelect}
        type="button"
      >
        <Badge tone={demonstrated ? "success" : "warning"}>
          {demonstrated ? "Evidence documented" : "Development priority"}
        </Badge>
        {selected ? <Badge tone="primary">Selected for plan</Badge> : null}
      </button>
      <button
        className="mt-auto inline-flex items-center gap-1 pt-3 text-sm font-semibold text-primary hover:text-primary-strong"
        onClick={onOpen}
        type="button"
      >
        Open
        <ArrowRight aria-hidden="true" className="size-3.5" />
      </button>
    </div>
  );
}

function InterviewSkillDetail({
  isPriorityFocus,
  node,
  onPractice,
  onShowOnMap,
  showPracticeAction,
  skillTotal,
}: {
  isPriorityFocus: boolean;
  node: RoadmapPathNode;
  onPractice: () => void;
  onShowOnMap: () => void;
  showPracticeAction: boolean;
  skillTotal: number;
}) {
  const { skill, globalIndex, stageName } = node;

  return (
    <article
      aria-labelledby={`interview-skill-${globalIndex}-title`}
      className="rounded-[var(--radius-card)] border border-line bg-surface px-5 py-5 sm:px-6 sm:py-6"
      id="interview-skill-detail"
    >
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 max-w-3xl">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            {isPriorityFocus ? (
              <Badge tone="primary">
                <Star aria-hidden="true" className="size-3 fill-current" />
                Priority focus
              </Badge>
            ) : null}
            <p className="text-xs font-semibold text-muted">
              Skill {globalIndex + 1} of {skillTotal}
              <span aria-hidden="true"> • </span>
              {stageName}
            </p>
          </div>
          <h4
            className="mt-3 font-display text-xl font-semibold tracking-[-0.02em] text-foreground sm:text-2xl"
            id={`interview-skill-${globalIndex}-title`}
          >
            {skill.name}
          </h4>
          <p className="mt-2 text-sm leading-7 text-muted">{skill.why}</p>
          {skill.howToStart ? (
            <div className="mt-4 rounded-[var(--radius-control)] border border-line bg-surface-subtle px-4 py-3">
              <p className="text-sm leading-6 text-muted-strong">
                <strong className="font-semibold text-foreground">
                  Recommended action:
                </strong>{" "}
                {skill.howToStart}
              </p>
            </div>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-col gap-2 sm:flex-row lg:flex-col">
          {showPracticeAction ? (
            <Button onClick={onPractice}>
              Open practice lab
              <ArrowRight aria-hidden="true" className="size-4" />
            </Button>
          ) : null}
          <Button onClick={onShowOnMap} variant="secondary">
            View on roadmap
          </Button>
        </div>
      </div>
    </article>
  );
}

function RoadmapHero({
  demonstrated,
  focus,
  progress,
  roleTitle,
  stages,
  total,
}: {
  demonstrated: number;
  focus: number;
  progress: number;
  roleTitle: string;
  stages: RoleRoadmap["stages"];
  total: number;
}) {
  return (
    <div className="relative overflow-hidden border-b border-line bg-navy px-5 py-7 text-white sm:px-8 sm:py-8">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_100%_0%,color-mix(in_srgb,var(--primary)_28%,transparent),transparent_55%),radial-gradient(ellipse_60%_50%_at_0%_100%,color-mix(in_srgb,var(--accent)_18%,transparent),transparent_50%)]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[0.12] [background-image:radial-gradient(rgb(255_255_255/0.5)_1px,transparent_1px)] [background-size:20px_20px]"
      />

      <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0 max-w-2xl">
          <p className="text-[0.6875rem] font-bold uppercase tracking-[0.16em] text-white/65">
            Role skill roadmap
          </p>
          <h3 className="mt-2 font-display text-2xl font-semibold tracking-[-0.03em] sm:text-[2rem] sm:leading-tight">
            Path to {roleTitle}
          </h3>
          <p className="mt-3 text-sm leading-6 text-white/72">
            A staged skill path from foundations to advanced topics. Hover any
            stop to preview why it matters and where to start.
          </p>
          <nav aria-label="Roadmap stages" className="mt-5">
            <ol className="flex flex-wrap gap-2">
              {stages.map((stage, stageIndex) => {
                const theme = stageTheme(stageIndex);
                const stageDemonstrated = stage.skills.filter(
                  (skill) => skill.alreadyDemonstrated,
                ).length;
                return (
                  <li key={stage.stage}>
                    <a
                      className={cn(
                        "rounded-full border px-3 py-1 text-xs font-semibold tracking-[-0.01em] text-white/90 underline-offset-4 transition-colors hover:bg-white/10 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white/50",
                        theme.chip,
                      )}
                      href={`#roadmap-stage-${stageIndex}`}
                    >
                      {stage.stage}
                      <span className="ml-1 tabular-nums text-white/70">
                        ({stageDemonstrated}/{stage.skills.length})
                      </span>
                    </a>
                  </li>
                );
              })}
            </ol>
          </nav>
        </div>

        <div className="flex flex-col gap-3 lg:items-end">
          <div className="flex flex-wrap items-center gap-4 lg:justify-end">
            <ProgressRing progress={progress} />
            <dl className="grid grid-cols-3 gap-2 sm:gap-3">
              <StatTile label="Skills" value={total} />
              <StatTile label="Evidence" value={demonstrated} />
              <StatTile label="Focus" value={focus} />
            </dl>
          </div>
          <p className="max-w-xs text-[0.6875rem] leading-5 text-white/55 lg:text-right">
            {EVIDENCE_COVERAGE_DISCLAIMER}
          </p>
        </div>
      </div>
    </div>
  );
}

function ProgressRing({ progress }: { progress: number }) {
  const radius = 34;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (progress / 100) * circumference;

  return (
    <div
      aria-label={`${progress}% of roadmap skills have evidence`}
      className="relative flex size-[5.5rem] shrink-0 items-center justify-center"
      role="img"
    >
      <svg
        aria-hidden="true"
        className="size-full -rotate-90"
        viewBox="0 0 80 80"
      >
        <circle
          className="text-white/15"
          cx="40"
          cy="40"
          fill="none"
          r={radius}
          stroke="currentColor"
          strokeWidth="5"
        />
        <circle
          className="text-primary transition-[stroke-dashoffset] duration-500 motion-reduce:transition-none"
          cx="40"
          cy="40"
          fill="none"
          r={radius}
          stroke="currentColor"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          strokeWidth="5"
        />
      </svg>
      <span className="absolute text-lg font-bold tabular-nums tracking-[-0.03em]">
        {progress}%
      </span>
    </div>
  );
}

function StatTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-[var(--radius-control)] border border-white/12 bg-white/8 px-3 py-2 backdrop-blur-sm">
      <p className="text-[0.625rem] font-bold uppercase tracking-[0.1em] text-white/55">
        {label}
      </p>
      <p className="text-xl font-semibold tabular-nums leading-tight">{value}</p>
    </div>
  );
}

function GrowthJourney({
  onToggleSkill,
  selected,
  stages,
  stageTotal,
}: {
  onToggleSkill: (name: string) => void;
  selected: ReadonlySet<string>;
  stages: RoleRoadmap["stages"];
  stageTotal: number;
}) {
  const nodes = buildRoadmapPath(stages);
  const prefersHover = usePrefersHover();
  const [hoveredSkill, setHoveredSkill] = useState<string | undefined>();
  const [pinnedSkill, setPinnedSkill] = useState<string | undefined>();

  const activeSkill = pinnedSkill ?? hoveredSkill;

  function revealSkill(name: string) {
    setHoveredSkill(name);
  }

  function hideSkill() {
    if (!pinnedSkill) setHoveredSkill(undefined);
  }

  function jumpToSkill(globalIndex: number) {
    const target = document.getElementById(`roadmap-skill-${globalIndex}`);
    target?.scrollIntoView({ behavior: "smooth", block: "center" });
    const node = nodes.find((item) => item.globalIndex === globalIndex);
    if (node) {
      setPinnedSkill(node.skill.name);
      setHoveredSkill(node.skill.name);
    }
  }

  return (
    <div>
      <nav
        aria-label="Skill navigator"
        className="mb-8 flex flex-wrap justify-center gap-2"
      >
        {nodes.map((node) => {
          const theme = stageTheme(node.stageIndex);
          const isActive = activeSkill === node.skill.name;
          return (
            <button
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-semibold transition-[border-color,background-color,transform] duration-200 motion-reduce:transition-none",
                isActive
                  ? cn(theme.chip, "scale-105 shadow-sm")
                  : "border-line bg-surface text-muted-strong hover:border-primary/30 hover:text-foreground",
              )}
              key={node.skill.name}
              onClick={() => jumpToSkill(node.globalIndex)}
              type="button"
            >
              <span className="tabular-nums">{node.globalIndex + 1}.</span>{" "}
              {node.skill.name}
            </button>
          );
        })}
      </nav>

      <div className="relative mx-auto max-w-3xl" role="list">
        <div
          aria-hidden="true"
          className="absolute top-4 bottom-4 left-1/2 w-px -translate-x-1/2 bg-gradient-to-b from-primary/25 via-line-strong to-warning-visual/25"
        />

        <div className="space-y-2">
          {nodes.map((node) => {
            const theme = stageTheme(node.stageIndex);
            const revealed = activeSkill === node.skill.name;
            const alignLeft = node.globalIndex % 2 === 0;

            return (
              <div key={node.skill.name} role="listitem">
                {node.isFirstInStage && (
                  <StageBand
                    id={`roadmap-stage-${node.stageIndex}`}
                    stageIndex={node.stageIndex}
                    stageName={node.stageName}
                    stageTotal={stageTotal}
                    theme={theme}
                  />
                )}

                <div className="grid grid-cols-1 gap-3 py-3 sm:grid-cols-[1fr_auto_1fr] sm:items-center sm:gap-5 sm:py-4">
                  {alignLeft ? (
                    <>
                      <GrowthSkillCard
                        align="left"
                        className="order-2 sm:order-none sm:col-start-1"
                        id={`roadmap-skill-${node.globalIndex}`}
                        onHide={hideSkill}
                        onReveal={() => revealSkill(node.skill.name)}
                        onTogglePin={() =>
                          setPinnedSkill((current) =>
                            current === node.skill.name ? undefined : node.skill.name,
                          )
                        }
                        onToggleSkill={() => onToggleSkill(node.skill.name)}
                        pinned={pinnedSkill === node.skill.name}
                        prefersHover={prefersHover}
                        revealed={revealed}
                        selected={selected.has(node.skill.name)}
                        skill={node.skill}
                        step={node.globalIndex + 1}
                        theme={theme}
                      />
                      <div className="order-1 flex justify-center sm:col-start-2 sm:row-start-1">
                        <RoadmapNodeDot
                          demonstrated={node.skill.alreadyDemonstrated}
                          revealed={revealed}
                          step={node.globalIndex + 1}
                          theme={theme}
                        />
                      </div>
                      <div
                        aria-hidden="true"
                        className="hidden sm:col-start-3 sm:block"
                      />
                    </>
                  ) : (
                    <>
                      <div
                        aria-hidden="true"
                        className="hidden sm:col-start-1 sm:block"
                      />
                      <div className="order-1 flex justify-center sm:col-start-2 sm:row-start-1">
                        <RoadmapNodeDot
                          demonstrated={node.skill.alreadyDemonstrated}
                          revealed={revealed}
                          step={node.globalIndex + 1}
                          theme={theme}
                        />
                      </div>
                      <GrowthSkillCard
                        align="right"
                        className="order-2 sm:order-none sm:col-start-3"
                        id={`roadmap-skill-${node.globalIndex}`}
                        onHide={hideSkill}
                        onReveal={() => revealSkill(node.skill.name)}
                        onTogglePin={() =>
                          setPinnedSkill((current) =>
                            current === node.skill.name ? undefined : node.skill.name,
                          )
                        }
                        onToggleSkill={() => onToggleSkill(node.skill.name)}
                        pinned={pinnedSkill === node.skill.name}
                        prefersHover={prefersHover}
                        revealed={revealed}
                        selected={selected.has(node.skill.name)}
                        skill={node.skill}
                        step={node.globalIndex + 1}
                        theme={theme}
                      />
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function StageBand({
  id,
  stageIndex,
  stageName,
  stageTotal,
  theme,
}: {
  id: string;
  stageIndex: number;
  stageName: string;
  stageTotal: number;
  theme: StageTheme;
}) {
  return (
    <div
      className={cn(
        "relative z-10 my-4 rounded-[var(--radius-control)] border px-4 py-2.5 text-center",
        theme.stageBar,
      )}
      id={id}
    >
      <p className="text-[0.625rem] font-bold uppercase tracking-[0.14em] text-muted">
        <span className="sr-only">
          Stage {stageIndex + 1} of {stageTotal}:{" "}
        </span>
        {stageName}
      </p>
    </div>
  );
}

function RoadmapNodeDot({
  demonstrated,
  revealed,
  step,
  theme,
}: {
  demonstrated: boolean;
  revealed: boolean;
  step: number;
  theme: StageTheme;
}) {
  return (
    <div
      className={cn(
        "relative z-10 flex size-11 items-center justify-center rounded-full ring-4 ring-background transition-transform duration-200 motion-reduce:transition-none sm:size-12",
        theme.dot,
        theme.dotRing,
        revealed && "scale-110",
      )}
    >
      {demonstrated ? (
        <CheckCircle2 aria-hidden="true" className="size-5" />
      ) : (
        <span className="text-sm font-bold tabular-nums">{step}</span>
      )}
    </div>
  );
}

function GrowthSkillCard({
  align,
  className,
  id,
  onHide,
  onReveal,
  onTogglePin,
  onToggleSkill,
  pinned,
  prefersHover,
  revealed,
  selected,
  skill,
  step,
  theme,
}: {
  align: "left" | "right";
  className?: string;
  id: string;
  onHide: () => void;
  onReveal: () => void;
  onTogglePin: () => void;
  onToggleSkill: () => void;
  pinned: boolean;
  prefersHover: boolean;
  revealed: boolean;
  selected: boolean;
  skill: RoadmapSkill;
  step: number;
  theme: StageTheme;
}) {
  const demonstrated = skill.alreadyDemonstrated;

  function handlePointerEnter() {
    if (prefersHover) onReveal();
  }

  function handlePointerLeave() {
    if (prefersHover) onHide();
  }

  function handleBlur(event: FocusEvent<HTMLDivElement>) {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
      onHide();
    }
  }

  return (
    <div
      className={cn(
        "group/card scroll-mt-24",
        align === "left" && "sm:pr-2",
        align === "right" && "sm:pl-2",
        className,
      )}
      data-roadmap-node=""
      id={id}
      onBlur={handleBlur}
      onFocus={() => onReveal()}
      onMouseEnter={handlePointerEnter}
      onMouseLeave={handlePointerLeave}
    >
      <div
        className={cn(
          "relative rounded-[var(--radius-card)] border bg-surface p-4 shadow-[var(--shadow-sm)] transition-[border-color,box-shadow,transform] duration-200 motion-reduce:transition-none",
          theme.card,
          theme.cardHover,
          revealed && "scale-[1.02] shadow-[var(--shadow-md)]",
          pinned && "ring-2 ring-primary/20 ring-offset-2",
          selected && "border-primary/35",
        )}
      >
        <div className="flex items-start gap-3">
          <label className="mt-0.5 shrink-0">
            <input
              aria-label={`Include ${skill.name} in your development plan`}
              checked={selected}
              className="size-4 accent-primary"
              onChange={onToggleSkill}
              type="checkbox"
            />
          </label>

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={cn(
                  "flex size-6 items-center justify-center rounded-full text-[0.6875rem] font-bold",
                  theme.dot,
                )}
              >
                {step}
              </span>
              <h4 className="min-w-0 text-sm font-semibold leading-snug tracking-[-0.02em] text-foreground sm:text-base">
                {skill.name}
              </h4>
            </div>

            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge tone={demonstrated ? "success" : "warning"}>
                {demonstrated ? "Evidence documented" : "Development priority"}
              </Badge>
              {selected ? <Badge tone="primary">Selected for plan</Badge> : null}
            </div>
          </div>
        </div>

        {revealed ? (
          <div className="mt-4 space-y-3 motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-top-1 motion-reduce:animate-none">
            <div className="rounded-[var(--radius-control)] border border-line bg-surface-subtle/80 p-3">
              <p className="text-sm leading-6 text-muted">{skill.why}</p>
              {skill.howToStart ? (
                <p className="mt-2 text-xs leading-5 text-muted-strong sm:text-sm">
                  <strong className={cn("font-semibold", theme.accent)}>
                    Start here:
                  </strong>{" "}
                  {skill.howToStart}
                </p>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                className="min-h-9 px-3 text-xs"
                onClick={onTogglePin}
                variant="ghost"
              >
                {pinned ? "Unpin details" : "Pin details"}
              </Button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
