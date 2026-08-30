"use client";

import {
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  Pencil,
  Trash2,
} from "lucide-react";
import { useRef, useState } from "react";

import { cn } from "@rezumi/ui";

import type { Skill } from "../api/types";
import {
  domainCircleSize,
  groupSkillsByDomain,
  type SkillDomain,
  type SkillDomainTone,
} from "./skill-domains";

/** Skills listed in the hover preview before it defers to the full list. */
const previewLimit = 8;

/**
 * Ring colours are applied inline rather than through `border-*` utilities:
 * `globals.css` sets `* { border-color: var(--border) }` outside any cascade
 * layer, which beats every layered Tailwind border-colour utility.
 */
const toneStyles: Record<
  SkillDomainTone,
  {
    chip: string;
    count: string;
    fill: string;
    ring: string;
    ringActive: string;
    selected: string;
  }
> = {
  ai: {
    chip: "bg-info-soft",
    count: "text-info-strong",
    fill: "bg-info-soft/40",
    ring: "color-mix(in srgb, var(--info) 55%, transparent)",
    ringActive: "var(--info)",
    selected:
      "shadow-[0_0_0_4px_color-mix(in_srgb,var(--info)_14%,transparent)]",
  },
  cloud: {
    chip: "bg-accent-soft",
    count: "text-accent-strong",
    fill: "bg-accent-soft/40",
    ring: "color-mix(in srgb, var(--accent) 55%, transparent)",
    ringActive: "var(--accent)",
    selected:
      "shadow-[0_0_0_4px_color-mix(in_srgb,var(--accent)_14%,transparent)]",
  },
  data: {
    chip: "bg-success-soft",
    count: "text-success-strong",
    fill: "bg-success-soft/40",
    ring: "color-mix(in srgb, var(--success) 55%, transparent)",
    ringActive: "var(--success)",
    selected:
      "shadow-[0_0_0_4px_color-mix(in_srgb,var(--success)_14%,transparent)]",
  },
  language: {
    chip: "bg-warning-soft",
    count: "text-warning-strong",
    fill: "bg-warning-soft/40",
    ring: "color-mix(in srgb, var(--warning) 60%, transparent)",
    ringActive: "var(--warning)",
    selected:
      "shadow-[0_0_0_4px_color-mix(in_srgb,var(--warning)_16%,transparent)]",
  },
  other: {
    chip: "bg-surface-subtle",
    count: "text-muted-strong",
    fill: "bg-surface",
    ring: "var(--border-strong)",
    ringActive: "var(--muted)",
    selected:
      "shadow-[0_0_0_4px_color-mix(in_srgb,var(--muted)_12%,transparent)]",
  },
  practice: {
    chip: "bg-primary-soft",
    count: "text-primary-strong",
    fill: "bg-primary-soft/40",
    ring: "color-mix(in srgb, var(--primary) 55%, transparent)",
    ringActive: "var(--primary)",
    selected:
      "shadow-[0_0_0_4px_color-mix(in_srgb,var(--primary)_14%,transparent)]",
  },
  web: {
    chip: "bg-danger-soft",
    count: "text-danger-strong",
    fill: "bg-danger-soft/35",
    ring: "color-mix(in srgb, var(--danger) 55%, transparent)",
    ringActive: "var(--danger)",
    selected:
      "shadow-[0_0_0_4px_color-mix(in_srgb,var(--danger)_14%,transparent)]",
  },
};

function countLabel(count: number): string {
  return `${count} ${count === 1 ? "skill" : "skills"} recorded`;
}

function DomainPreview({
  domain,
  onShowAll,
  placement,
}: {
  domain: SkillDomain;
  onShowAll: () => void;
  placement: "left" | "right";
}) {
  const shown = domain.skills.slice(0, previewLimit);
  const remaining = domain.skills.length - shown.length;
  return (
    <div
      className={cn(
        "absolute top-1/2 z-30 w-[21.5rem] -translate-y-1/2",
        placement === "right" ? "left-full pl-6" : "right-full pr-6",
      )}
      role="presentation"
    >
      <span
        aria-hidden="true"
        className={cn(
          "absolute top-1/2 h-px w-6 -translate-y-1/2 bg-line-strong",
          placement === "right" ? "left-0" : "right-0",
        )}
      />
      <span
        aria-hidden="true"
        className={cn(
          "absolute top-1/2 size-1.5 -translate-y-1/2 rounded-full bg-line-strong",
          placement === "right" ? "left-0" : "right-0",
        )}
      />
      <div className="rounded-[var(--radius-card)] border border-line bg-surface p-4 shadow-[var(--shadow-lg)]">
        <ul className="grid gap-x-5 gap-y-2.5 sm:grid-cols-2">
          {shown.map((skill) => (
            <li
              className="flex items-center gap-2.5 text-[0.8125rem]"
              key={skill.id}
            >
              {skill.userConfirmed ? (
                <CheckCircle2
                  aria-hidden="true"
                  className="size-4 shrink-0 text-success"
                />
              ) : (
                <CircleAlert
                  aria-hidden="true"
                  className="size-4 shrink-0 text-warning"
                />
              )}
              <span className="truncate text-foreground">{skill.name}</span>
            </li>
          ))}
        </ul>
        {remaining > 0 && (
          <div className="mt-3 border-t border-line pt-2.5">
            <button
              className="text-[0.8125rem] font-semibold text-info hover:underline"
              onClick={onShowAll}
              type="button"
            >
              + {remaining} more
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Skills as clusters rather than rows.
 *
 * A career record accumulates dozens of named skills; a flat table makes them
 * unreadable. Each circle is one derived domain sized by how many recorded
 * skills it holds. Hovering or focusing a circle previews its skills; selecting
 * one opens the full, editable list underneath — the preview stays read-only so
 * a pointer passing over a circle can never trigger a record change.
 */
export function SkillConstellation({
  evidenceCounts,
  onConfirm,
  onDelete,
  onEdit,
  skills,
}: {
  evidenceCounts: Record<string, number> | undefined;
  onConfirm: (skill: Skill) => void;
  onDelete: (skill: Skill) => void;
  onEdit: (skill: Skill) => void;
  skills: Skill[];
}) {
  const domains = groupSkillsByDomain(skills);
  const [preview, setPreview] = useState<{
    id: string;
    placement: "left" | "right";
  }>();
  const [selectedId, setSelectedId] = useState<string>();
  const [expanded, setExpanded] = useState(false);
  const gridRef = useRef<HTMLUListElement>(null);

  const selected =
    domains.find((domain) => domain.id === selectedId) ?? domains[0];

  if (domains.length === 0) {
    return (
      <p className="px-4 py-8 text-center text-[0.8125rem] text-muted sm:px-5">
        No skills added. A skill name never implies evidence or proficiency on
        its own.
      </p>
    );
  }

  /** Flip the preview to whichever side keeps it inside the panel. */
  function openPreview(id: string, circle: HTMLButtonElement) {
    const bounds = gridRef.current?.getBoundingClientRect();
    const anchor = circle.getBoundingClientRect();
    const fitsRight = bounds ? anchor.right + 368 <= bounds.right : true;
    setPreview({ id, placement: fitsRight ? "right" : "left" });
  }

  function selectDomain(id: string) {
    setSelectedId(id);
    setExpanded(true);
    setPreview(undefined);
  }

  return (
    <div>
      <ul
        aria-label="Skill domains"
        className="flex flex-wrap items-start gap-x-8 gap-y-6 px-4 py-6 sm:px-6"
        ref={gridRef}
      >
        {domains.map((domain) => {
          const tone = toneStyles[domain.tone];
          const size = domainCircleSize(domain.skills.length);
          const showing = preview?.id === domain.id;
          return (
            <li
              className="relative flex flex-col items-center"
              key={domain.id}
              onPointerLeave={() => setPreview(undefined)}
            >
              <button
                aria-label={`${domain.label} skill domain, ${countLabel(domain.skills.length)}`}
                className={cn(
                  "grid place-items-center rounded-full border-2 transition-[border-color,box-shadow] duration-200 motion-reduce:transition-none",
                  tone.fill,
                  (showing || selected?.id === domain.id) && tone.selected,
                )}
                onBlur={() => setPreview(undefined)}
                onClick={() => selectDomain(domain.id)}
                onFocus={(event) => openPreview(domain.id, event.currentTarget)}
                onPointerEnter={(event) =>
                  openPreview(domain.id, event.currentTarget)
                }
                style={{
                  borderColor:
                    showing || selected?.id === domain.id
                      ? tone.ringActive
                      : tone.ring,
                  height: size,
                  width: size,
                }}
                type="button"
              >
                <span
                  className={cn(
                    "text-[1.75rem] font-bold leading-none tabular-nums",
                    tone.count,
                  )}
                >
                  {domain.skills.length}
                </span>
              </button>
              <p
                className="mt-2.5 max-w-[8rem] text-center text-[0.8125rem] font-semibold text-foreground"
                style={{ minWidth: size }}
              >
                {domain.label}
              </p>
              {showing && (
                <DomainPreview
                  domain={domain}
                  onShowAll={() => selectDomain(domain.id)}
                  placement={preview.placement}
                />
              )}
            </li>
          );
        })}
      </ul>

      {selected && (
        <div className="border-t border-line">
          <button
            aria-controls="skill-domain-detail"
            aria-expanded={expanded}
            className="flex w-full items-center gap-3 px-4 py-4 text-left transition-colors hover:bg-surface-subtle/50 sm:px-6"
            onClick={() => setExpanded((value) => !value)}
            type="button"
          >
            <span className="text-[0.9375rem] font-bold text-foreground">
              {selected.label}
            </span>
            <span className="text-[0.8125rem] text-muted">
              {countLabel(selected.skills.length)}
            </span>
            <ChevronDown
              aria-hidden="true"
              className={cn(
                "ml-auto size-5 shrink-0 text-muted transition-transform duration-200 motion-reduce:transition-none",
                expanded && "rotate-180",
              )}
            />
          </button>
          {expanded && (
            <div
              className="border-t border-line bg-surface-subtle/45 px-4 py-4 sm:px-6"
              id="skill-domain-detail"
            >
              <ul className="flex flex-wrap gap-2">
                {selected.skills.map((skill) => {
                  const evidence = evidenceCounts
                    ? (evidenceCounts[skill.id] ?? 0)
                    : undefined;
                  return (
                    <li
                      className={cn(
                        "flex items-center gap-2 rounded-[var(--radius-pill)] border border-line py-1 pl-3 pr-1.5 text-[0.8125rem]",
                        toneStyles[selected.tone].chip,
                      )}
                      key={skill.id}
                    >
                      {skill.userConfirmed ? (
                        <CheckCircle2
                          aria-label="Confirmed"
                          className="size-3.5 shrink-0 text-success"
                        />
                      ) : (
                        <CircleAlert
                          aria-label="Needs review"
                          className="size-3.5 shrink-0 text-warning"
                        />
                      )}
                      <span className="font-semibold text-foreground">
                        {skill.name}
                      </span>
                      {skill.proficiency && (
                        <span className="text-[0.6875rem] text-muted">
                          {skill.proficiency}
                        </span>
                      )}
                      {evidence !== undefined && evidence > 0 && (
                        <span className="text-[0.6875rem] tabular-nums text-muted">
                          {evidence}{" "}
                          {evidence === 1 ? "evidence item" : "evidence items"}
                        </span>
                      )}
                      {!skill.userConfirmed && (
                        <button
                          aria-label={`Confirm ${skill.name}`}
                          className="rounded-[var(--radius-pill)] px-2 text-[0.6875rem] font-bold text-info hover:underline"
                          onClick={() => onConfirm(skill)}
                          type="button"
                        >
                          Confirm
                        </button>
                      )}
                      <button
                        aria-label={`Edit ${skill.name}`}
                        className="grid size-6 shrink-0 place-items-center rounded-full text-muted transition-colors hover:bg-surface hover:text-foreground"
                        onClick={() => onEdit(skill)}
                        title={`Edit ${skill.name}`}
                        type="button"
                      >
                        <Pencil aria-hidden="true" className="size-3.5" />
                      </button>
                      <button
                        aria-label={`Delete ${skill.name}`}
                        className="grid size-6 shrink-0 place-items-center rounded-full text-muted transition-colors hover:bg-danger-soft hover:text-danger"
                        onClick={() => onDelete(skill)}
                        title={`Delete ${skill.name}`}
                        type="button"
                      >
                        <Trash2 aria-hidden="true" className="size-3.5" />
                      </button>
                    </li>
                  );
                })}
              </ul>
              <p className="mt-3 text-xs leading-5 text-muted">
                Domains group the skills you recorded so they stay readable.
                They are a display grouping only — no skill, proficiency, or
                evidence is inferred from them.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
