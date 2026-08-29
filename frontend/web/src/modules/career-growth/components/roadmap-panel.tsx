"use client";

import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Badge,
  Button,
  EmptyState,
  LoadingSkeleton,
  cn,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import { confirmRoleRoadmap, getRoleRoadmap } from "../api/career-growth-api";
import type { RoleRoadmap } from "../api/types";

/**
 * "Your roadmap": resolves the owner's target role, shows the curated skill
 * roadmap for it, and marks skills they already have evidence for (dashed
 * card) so they can opt out of what they already know before confirming.
 * Confirming creates planned development items, which then show up in the
 * existing development-item list/status control below — no new tracking
 * mechanism, just the one that's already there.
 */
export function RoadmapPanel({ onConfirmed }: { onConfirmed: () => void }) {
  const [roadmap, setRoadmap] = useState<RoleRoadmap | null>();
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [failure, setFailure] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
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
      onConfirmed();
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "Your roadmap could not be confirmed."),
      );
    } finally {
      setBusy(false);
    }
  }

  if (roadmap === undefined) {
    return <LoadingSkeleton className="p-4" />;
  }

  if (roadmap === null) {
    return (
      <EmptyState
        description="Set a target role in Role Readiness, or save at least one experience, so we can suggest a roadmap."
        title="No target role yet"
      />
    );
  }

  return (
    <div className="space-y-4">
      {failure && (
        <Alert title="Roadmap unavailable" tone="danger">
          {failure}
        </Alert>
      )}
      {success && (
        <Alert title="Added" tone="success">
          {success}
        </Alert>
      )}
      <p className="text-sm text-muted">
        Roadmap for{" "}
        <strong className="font-bold text-foreground">
          {roadmap.roleTitle}
        </strong>
        . Skills you already have evidence for are marked and unchecked by
        default — check them back in if you still want to work through them, or
        uncheck anything else you&apos;d rather skip.
      </p>
      {roadmap.stages.map((stage) => (
        <div key={stage.stage}>
          <h3 className="text-xs font-black uppercase tracking-wide text-muted">
            {stage.stage}
          </h3>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {stage.skills.map((skill) => (
              <label
                className={cn(
                  "rounded-lg border p-3 text-sm",
                  skill.alreadyDemonstrated
                    ? "border-dashed border-line-strong bg-surface-subtle"
                    : "border-line bg-surface",
                )}
                key={skill.name}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="font-bold text-foreground">
                    {skill.name}
                  </span>
                  <input
                    checked={selected.has(skill.name)}
                    className="mt-1 size-4 accent-primary"
                    onChange={() => toggle(skill.name)}
                    type="checkbox"
                  />
                </div>
                {skill.alreadyDemonstrated && (
                  <Badge className="mt-2" tone="neutral">
                    Already familiar
                  </Badge>
                )}
                <p className="mt-2 text-xs leading-5 text-muted">{skill.why}</p>
              </label>
            ))}
          </div>
        </div>
      ))}
      <Button loading={busy} onClick={() => void confirm()}>
        Confirm my roadmap
      </Button>
    </div>
  );
}
