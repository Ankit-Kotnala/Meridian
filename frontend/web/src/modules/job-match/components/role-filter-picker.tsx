"use client";

import { X } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";

import { Badge, Button, Card, Input } from "@rezumi/ui";

/**
 * Lets an owner opt in/out of the roles used to filter "Suggested for you".
 * `selected` is empty until the owner makes an explicit choice — until then
 * the auto-suggested roles are shown (and removing one of them makes the
 * remainder an explicit selection, rather than silently reverting later).
 */
export function RoleFilterPicker({
  action,
  busy,
  onChange,
  selected,
  suggested,
}: {
  action?: ReactNode;
  busy: boolean;
  onChange: (next: string[]) => void;
  selected: string[];
  suggested: string[];
}) {
  const [draft, setDraft] = useState("");
  const isExplicit = selected.length > 0;
  const active = isExplicit ? selected : suggested;

  function addTitle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const title = draft.trim();
    if (!title) return;
    const base = isExplicit ? selected : suggested;
    if (base.includes(title)) {
      setDraft("");
      return;
    }
    onChange([...base, title]);
    setDraft("");
  }

  function removeTitle(title: string) {
    const base = isExplicit ? selected : suggested;
    onChange(base.filter((item) => item !== title));
  }

  return (
    <Card as="section" aria-labelledby="role-filter-heading">
      <div className="flex flex-col gap-3 p-4 lg:flex-row lg:items-center lg:gap-4">
        <p
          className="shrink-0 text-sm font-semibold text-foreground"
          id="role-filter-heading"
          title={
            isExplicit
              ? "Showing jobs for the roles you chose."
              : "Auto-suggested from your career record. Add or remove roles to customize."
          }
        >
          Roles you want to see jobs for
        </p>

        <ul className="flex flex-wrap items-center gap-2">
          {active.length === 0 && (
            <li className="text-xs text-muted">
              No roles selected yet — add one below.
            </li>
          )}
          {active.map((title) => (
            <li key={title}>
              <Badge
                className="inline-flex items-center gap-1.5"
                tone={isExplicit ? "primary" : "neutral"}
              >
                {title}
                <button
                  aria-label={`Remove ${title}`}
                  disabled={busy}
                  onClick={() => removeTitle(title)}
                  type="button"
                >
                  <X aria-hidden="true" className="size-3" />
                </button>
              </Badge>
            </li>
          ))}
        </ul>

        <form
          className="flex flex-1 gap-2 lg:min-w-[18rem]"
          onSubmit={addTitle}
        >
          <Input
            aria-label="Add a role title"
            maxLength={200}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Add a role title, e.g. Staff Data Engineer"
            value={draft}
          />
          <Button disabled={busy} type="submit" variant="secondary">
            Add
          </Button>
        </form>

        {action && <div className="shrink-0">{action}</div>}
      </div>
    </Card>
  );
}
