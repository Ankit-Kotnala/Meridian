"use client";

import { X } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Badge, Button, Input } from "@rezumi/ui";

/**
 * Lets an owner opt in/out of the roles used to filter "Suggested for you".
 * `selected` is empty until the owner makes an explicit choice — until then
 * the auto-suggested roles are shown (and removing one of them makes the
 * remainder an explicit selection, rather than silently reverting later).
 */
export function RoleFilterPicker({
  busy,
  onChange,
  selected,
  suggested,
}: {
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
    <div>
      <p className="text-sm font-bold text-foreground">
        Roles you want to see jobs for
      </p>
      <p className="mt-1 text-xs text-muted">
        {isExplicit
          ? "Showing jobs for the roles you chose below."
          : "Auto-suggested from your career record. Add or remove roles to customize."}
      </p>
      <ul className="mt-3 flex flex-wrap gap-2">
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
      <form className="mt-3 flex gap-2" onSubmit={addTitle}>
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
    </div>
  );
}
