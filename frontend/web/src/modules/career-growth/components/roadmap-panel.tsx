"use client";

import {
  ArrowRight,
  CheckCircle2,
  Circle,
  RefreshCcw,
  Sparkles,
  Target,
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
    cardHover: "hover:shadow-[0_12px_32px_color-mix(in_srgb,var(--primary)_14%,transparent)]",
    accent: "text-primary",
    spine: "bg-primary/35",
  },
  {
    chip: "bg-success-soft text-success border-success/15",
    dot: "bg-success text-white",
    dotRing: "ring-success/25",
    stageBar: "border-success/20 bg-success-soft/80",
    card: "border-success/12 hover:border-success/30",
    cardHover: "hover:shadow-[0_12px_32px_color-mix(in_srgb,var(--success)_14%,transparent)]",
    accent: "text-success",
    spine: "bg-success/35",
  },
  {
    chip: "bg-warning-soft text-warning border-warning-visual/15",
    dot: "bg-warning-visual text-white",
    dotRing: "ring-warning-visual/25",
    stageBar: "border-warning-visual/20 bg-warning-soft/80",
    card: "border-warning-visual/12 hover:border-warning-visual/35",
    cardHover: "hover:shadow-[0_12px_32px_color-mix(in_srgb,var(--warning-visual)_14%,transparent)]",
    accent: "text-warning",
    spine: "bg-warning-visual/35",
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

/**
 * "Your roadmap": resolves the owner's target role, shows the curated skill
 * path for it, and marks skills they already have evidence for so they can
 * opt out of what they already know before confirming.
 */
export function RoadmapPanel({ onConfirmed }: { onConfirmed?: () => void }) {
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

        <RoadmapJourney
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
            Your learning roadmap
          </p>
          <h3 className="mt-2 font-[family-name:var(--font-family-display)] text-2xl font-semibold tracking-[-0.03em] sm:text-[2rem] sm:leading-tight">
            Your path to {roleTitle}
          </h3>
          <p className="mt-3 text-sm leading-6 text-white/72">
            A staged skill path from foundations to advanced topics. Hover any
            stop to preview why it matters and where to start.
          </p>
          <nav aria-label="Roadmap stages" className="mt-5">
            <ol className="flex flex-wrap gap-2">
              {stages.map((stage, stageIndex) => {
                const theme = stageTheme(stageIndex);
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
                    </a>
                  </li>
                );
              })}
            </ol>
          </nav>
        </div>

        <div className="flex flex-wrap items-center gap-4 lg:justify-end">
          <ProgressRing progress={progress} />
          <dl className="grid grid-cols-3 gap-2 sm:gap-3">
            <StatTile label="Skills" value={total} />
            <StatTile label="Evidence" value={demonstrated} />
            <StatTile label="Focus" value={focus} />
          </dl>
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
      <p className="text-xl font-semibold tabular-nums leading-tight">
        {value}
      </p>
    </div>
  );
}

function RoadmapJourney({
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

  return (
    <div className="relative mx-auto max-w-3xl" role="list">
      <div
        aria-hidden="true"
        className="absolute top-4 bottom-4 left-1/2 w-px -translate-x-1/2 bg-gradient-to-b from-line via-line-strong to-line"
      />

      <div className="space-y-2">
        {nodes.map((node) => {
          const theme = stageTheme(node.stageIndex);
          const revealed = hoveredSkill === node.skill.name;
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
                    <RoadmapSkillCard
                      align="left"
                      className="order-2 sm:order-none sm:col-start-1"
                      onHide={() => setHoveredSkill(undefined)}
                      onReveal={() => setHoveredSkill(node.skill.name)}
                      onToggleSkill={() => onToggleSkill(node.skill.name)}
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
                    <RoadmapSkillCard
                      align="right"
                      className="order-2 sm:order-none sm:col-start-3"
                      onHide={() => setHoveredSkill(undefined)}
                      onReveal={() => setHoveredSkill(node.skill.name)}
                      onToggleSkill={() => onToggleSkill(node.skill.name)}
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

function RoadmapSkillCard({
  align,
  className,
  onHide,
  onReveal,
  onToggleSkill,
  prefersHover,
  revealed,
  selected,
  skill,
  step,
  theme,
}: {
  align: "left" | "right";
  className?: string;
  onHide: () => void;
  onReveal: () => void;
  onToggleSkill: () => void;
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
        "group/card",
        align === "left" && "sm:pr-2",
        align === "right" && "sm:pl-2",
        className,
      )}
      data-roadmap-node=""
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
                {demonstrated ? (
                  <>
                    <CheckCircle2 aria-hidden="true" className="size-3" />
                    Evidence found
                  </>
                ) : (
                  <>
                    <Target aria-hidden="true" className="size-3" />
                    Suggested focus
                  </>
                )}
              </Badge>
              {selected && (
                <Badge tone="primary">
                  <Circle aria-hidden="true" className="size-2 fill-current" />
                  In plan
                </Badge>
              )}
            </div>
          </div>
        </div>

        {revealed ? (
          <div className="mt-4 rounded-[var(--radius-control)] border border-line bg-surface-subtle/80 p-3 motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-top-1 motion-reduce:animate-none">
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
        ) : null}
      </div>
    </div>
  );
}
