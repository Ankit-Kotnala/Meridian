"use client";

import { useState } from "react";

import { Button, Input, Select } from "@careeros/ui";

import type { Application, ApplicationStage } from "../api/types";
import { allowedStageTransitions, humanize } from "./application-options";

type ApplicationStageControlProps = {
  application: Application;
  busy?: boolean;
  compact?: boolean;
  onMove: (
    application: Application,
    stage: ApplicationStage,
    reopenReason?: string,
  ) => void;
};

export function ApplicationStageControl(props: ApplicationStageControlProps) {
  return (
    <ApplicationStageControlForStage key={props.application.stage} {...props} />
  );
}

function ApplicationStageControlForStage({
  application,
  busy = false,
  compact = false,
  onMove,
}: ApplicationStageControlProps) {
  const [nextStage, setNextStage] = useState<ApplicationStage>(
    application.stage,
  );
  const [reopenReason, setReopenReason] = useState("");

  const reopening =
    (application.stage === "rejected" || application.stage === "withdrawn") &&
    nextStage !== application.stage;
  const availableStages = [
    application.stage,
    ...allowedStageTransitions[application.stage],
  ];

  return (
    <div
      className={
        compact
          ? "grid gap-2"
          : "flex min-w-52 flex-col gap-2 sm:flex-row sm:items-end"
      }
    >
      <label className="min-w-0 flex-1 text-xs font-bold text-muted">
        <span className={compact ? "sr-only" : undefined}>Move to stage</span>
        <Select
          aria-label={
            compact ? `Move ${application.jobTitle} to stage` : undefined
          }
          className={compact ? "" : "mt-1"}
          disabled={busy}
          onChange={(event) =>
            setNextStage(event.target.value as ApplicationStage)
          }
          value={nextStage}
        >
          {availableStages.map((stage) => (
            <option key={stage} value={stage}>
              {humanize(stage)}
            </option>
          ))}
        </Select>
      </label>
      {reopening && (
        <label className="text-xs font-bold text-muted">
          Reason for reopening
          <Input
            className="mt-1 min-h-9"
            maxLength={500}
            onChange={(event) => setReopenReason(event.target.value)}
            required
            value={reopenReason}
          />
        </label>
      )}
      <Button
        className="min-h-9 px-3"
        disabled={
          nextStage === application.stage || (reopening && !reopenReason.trim())
        }
        loading={busy}
        onClick={() =>
          onMove(application, nextStage, reopenReason.trim() || undefined)
        }
        type="button"
        variant="secondary"
      >
        Move
      </Button>
    </div>
  );
}
