"use client";

import { ArrowRight, ChevronDown, RefreshCcw, Sparkles } from "lucide-react";
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
    };
  }, [roadmap]);

  if (loading) {
    return (
      <div aria-label="Loading personalized roadmap" role="status">
        <LoadingSkeleton className="min-h-56 p-4" />
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
    <div className="surface-card rounded-[var(--radius-card)]">
      <div className="border-b border-line bg-surface-subtle p-5 sm:p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <Badge tone="primary">Personalized at runtime</Badge>
            <h3 className="mt-3 text-xl font-semibold tracking-[-0.025em] text-foreground sm:text-2xl">
              Your path to {roadmap.roleTitle}
            </h3>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
              Follow the stages in order. Hover a stop or activate its name to
              see why it matters and a concrete first step. A suggested focus
              means we did not find a current evidence signal, not that you do
              not have the skill.
            </p>
            <ol className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm font-semibold text-foreground">
              {roadmap.stages.map((stage, stageIndex) => (
                <li className="flex items-center gap-2" key={stage.stage}>
                  {stageIndex > 0 && (
                    <ArrowRight
                      aria-hidden="true"
                      className="size-3.5 text-primary/70"
                    />
                  )}
                  <a
                    className="rounded-[var(--radius-small)] text-primary underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                    href={`#roadmap-stage-${stageIndex}`}
                  >
                    {stage.stage}
                  </a>
                </li>
              ))}
            </ol>
          </div>
          <dl className="grid shrink-0 grid-cols-2 gap-2 sm:min-w-64">
            <div className="rounded-[var(--radius-control)] border border-line bg-surface p-3">
              <dt className="text-[0.6875rem] font-bold uppercase tracking-[0.1em] text-muted">
                Evidence found
              </dt>
              <dd className="mt-1 text-2xl font-semibold text-foreground">
                {summary.demonstrated}
              </dd>
            </div>
            <div className="rounded-[var(--radius-control)] border border-line bg-surface p-3">
              <dt className="text-[0.6875rem] font-bold uppercase tracking-[0.1em] text-muted">
                Focus areas
              </dt>
              <dd className="mt-1 text-2xl font-semibold text-foreground">
                {summary.focus}
              </dd>
            </div>
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
        <p className="mb-5 text-sm text-muted">
          Roadmap for{" "}
          <strong className="font-bold text-foreground">
            {roadmap.roleTitle}
          </strong>
          . Skills with evidence are unmarked by default — check them back in if
          you still want to work through them, or uncheck anything else you
          would rather skip.
        </p>
        <ol className="relative">
          <span
            aria-hidden="true"
            className="absolute bottom-8 left-4 top-4 w-px bg-gradient-to-b from-primary via-primary/45 to-border-strong sm:left-5"
          />
          {roadmap.stages.map((stage, stageIndex) => (
            <li
              className="relative grid grid-cols-[2rem_minmax(0,1fr)] gap-3 pb-8 last:pb-0 sm:grid-cols-[2.5rem_minmax(0,1fr)] sm:gap-5"
              key={stage.stage}
            >
              <div className="relative z-10 flex justify-center">
                <span className="flex size-8 items-center justify-center rounded-full border-2 border-primary bg-surface text-sm font-semibold tabular-nums text-primary shadow-[0_0_0_4px_var(--surface)] sm:size-10 sm:text-base">
                  <span className="sr-only">Stage </span>
                  {stageIndex + 1}
                </span>
              </div>
              <section className="min-w-0 pt-0.5 sm:pt-1.5">
                <p className="text-[0.6875rem] font-bold uppercase tracking-[0.12em] text-primary">
                  Stage {stageIndex + 1} of {summary.stages}
                </p>
                <h4
                  className="mt-1 text-base font-semibold tracking-[-0.02em] text-foreground"
                  id={`roadmap-stage-${stageIndex}`}
                >
                  {stage.stage}
                </h4>
                <ol className="mt-4 space-y-3">
                  {stage.skills.map((skill, skillIndex) => (
                    <RoadmapStop
                      expanded={openSkill === skill.name}
                      key={skill.name}
                      offset={skillIndex % 2 === 1}
                      onToggle={() => toggle(skill.name)}
                      onToggleDetails={() =>
                        setOpenSkill((current) =>
                          current === skill.name ? undefined : skill.name,
                        )
                      }
                      selected={selected.has(skill.name)}
                      skill={skill}
                    />
                  ))}
                </ol>
              </section>
            </li>
          ))}
        </ol>
        <div className="mt-2 flex flex-col gap-3 border-t border-line pt-5 sm:flex-row sm:items-center sm:justify-between">
          <p className="flex items-start gap-2 text-sm text-muted">
            <Sparkles
              aria-hidden="true"
              className="mt-0.5 size-4 shrink-0 text-primary"
            />
            {selected.size} {selected.size === 1 ? "skill" : "skills"} selected
            for your development plan.
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

function canHoverRevealDetails() {
  return Boolean(
    window.matchMedia?.("(hover: hover) and (pointer: fine)").matches,
  );
}

function RoadmapStop({
  expanded,
  offset,
  onToggle,
  onToggleDetails,
  selected,
  skill,
}: {
  expanded: boolean;
  offset: boolean;
  onToggle: () => void;
  onToggleDetails: () => void;
  selected: boolean;
  skill: RoadmapSkill;
}) {
  const detailId = useId();
  const [hovered, setHovered] = useState(false);
  const showDetails = expanded || hovered;

  return (
    <li
      className={cn("min-w-0", offset && "sm:ml-8 lg:ml-12")}
      onMouseEnter={() => {
        if (canHoverRevealDetails()) setHovered(true);
      }}
      onMouseLeave={() => setHovered(false)}
    >
      <div
        className={cn(
          "relative rounded-[var(--radius-control)] border bg-surface p-3.5 transition-[border-color,background-color] duration-200 motion-reduce:transition-none",
          selected
            ? "border-primary bg-primary-soft/30"
            : "border-line hover:border-primary/40",
        )}
      >
        <span
          aria-hidden="true"
          className={cn(
            "pointer-events-none absolute top-6 right-full h-px bg-border-strong",
            offset
              ? "w-[1.75rem] sm:w-[4.5rem] lg:w-[5.5rem]"
              : "w-[1.75rem] sm:w-[2.5rem]",
          )}
        />
        <div className="flex items-start gap-3">
          <span
            aria-hidden="true"
            className={cn(
              "mt-1.5 size-2.5 shrink-0 rounded-full border-2",
              skill.alreadyDemonstrated
                ? "border-success bg-success"
                : "border-warning bg-warning-visual",
            )}
          />
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-3">
              <button
                aria-controls={detailId}
                aria-expanded={showDetails}
                className="inline-flex min-w-0 items-start gap-1.5 rounded-[var(--radius-small)] text-left text-sm font-semibold tracking-[-0.01em] text-foreground hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
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
              tone={skill.alreadyDemonstrated ? "success" : "warning"}
            >
              {skill.alreadyDemonstrated ? "Evidence found" : "Suggested focus"}
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
                  <p className="mt-3 rounded-md bg-surface-subtle px-3 py-2 text-xs leading-5 text-muted-strong">
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
