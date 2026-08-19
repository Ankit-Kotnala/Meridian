"use client";

import { CheckCircle2, Loader, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Badge, cn } from "@rezumi/ui";

import { runAutoImport } from "../auto-import/run-auto-import";

type RunState =
  | { kind: "applying"; done: number; total: number }
  | { kind: "done"; applied: number; held: number; questions: number }
  | { kind: "failed"; applied: number; message: string }
  | { kind: "idle" };

/**
 * Derives import proposals from the reviewed resume, then applies every
 * unambiguous one without prompting.
 *
 * Proposal creation runs here because nothing else triggers it: without this
 * call a reviewed resume produced no proposals at all, so the career record
 * stayed empty and the workspace never finished activating. The endpoint is
 * idempotent on (snapshot, semantic entity), so re-running it on every
 * dashboard visit re-derives nothing and creates no duplicates.
 *
 * Fields reach this point only after a person confirmed them in typed resume
 * review, so a second accept step was pure friction. Anything ambiguous is left
 * for review and reported here rather than written silently.
 */
export function AutoImportRunner({
  documentId,
  snapshotId,
}: {
  /** Reviewed source to derive proposals from, absent until a report exists. */
  documentId?: string;
  snapshotId?: string;
}) {
  const [state, setState] = useState<RunState>({ kind: "idle" });
  const started = useRef(false);
  const router = useRouter();

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    let active = true;

    async function run() {
      let applied = 0;
      try {
        const result = await runAutoImport(documentId, snapshotId, (progress) => {
          if (!active || progress.total === 0) return;
          setState({
            done: progress.done,
            kind: "applying",
            total: progress.total,
          });
        });
        if (!active) return;

        applied = result.applied;
        if (
          result.applied === 0 &&
          result.held === 0 &&
          result.questions === 0
        ) {
          return;
        }

        setState({
          applied: result.applied,
          held: result.held,
          kind: "done",
          questions: result.questions,
        });
        router.refresh();
      } catch (error) {
        if (!active) return;
        setState({
          applied,
          kind: "failed",
          message:
            error instanceof Error
              ? error.message
              : "Some resume facts could not be added automatically.",
        });
        if (applied > 0) router.refresh();
      }
    }

    queueMicrotask(() => void run());
    return () => {
      active = false;
    };
  }, [documentId, router, snapshotId]);

  if (state.kind === "idle") return null;
  if (
    state.kind === "done" &&
    state.applied === 0 &&
    state.held === 0 &&
    state.questions === 0
  ) {
    return null;
  }

  const tone =
    state.kind === "failed"
      ? "border-danger/30 bg-danger-soft/50"
      : state.kind === "applying"
        ? "border-primary/30 bg-primary-soft/45"
        : "border-success/30 bg-success-soft/45";

  return (
    <section
      aria-live="polite"
      className={cn(
        "flex flex-wrap items-center gap-3 rounded-[var(--radius-card)] border p-4 sm:px-5",
        tone,
      )}
    >
      <span className="grid size-9 shrink-0 place-items-center rounded-full bg-surface/80">
        {state.kind === "applying" ? (
          <Loader
            aria-hidden="true"
            className="size-4 animate-spin text-primary"
          />
        ) : state.kind === "failed" ? (
          <TriangleAlert aria-hidden="true" className="size-4 text-danger" />
        ) : (
          <CheckCircle2
            aria-hidden="true"
            className="size-4 text-success-strong"
          />
        )}
      </span>

      <div className="min-w-0 flex-1">
        {state.kind === "applying" && (
          <>
            <p className="text-sm font-semibold text-foreground">
              Adding your reviewed resume facts to your career record…
            </p>
            <p className="mt-0.5 text-xs text-muted">
              {state.done} of {state.total} applied. You already confirmed these
              during resume review.
            </p>
          </>
        )}
        {state.kind === "done" && (
          <>
            <p className="text-sm font-semibold text-foreground">
              {state.applied > 0
                ? `${state.applied} reviewed ${state.applied === 1 ? "fact" : "facts"} added to your career record automatically.`
                : "Your reviewed resume facts need a decision."}
            </p>
            <p className="mt-0.5 text-xs text-muted">
              {state.held > 0 ? (
                <>
                  {state.held}{" "}
                  {state.held === 1 ? "item conflicts" : "items conflict"} or
                  could not be traced to your file, so{" "}
                  {state.held === 1 ? "it is" : "they are"} waiting for you.{" "}
                  <Link className="text-link" href="/career-profile/imports">
                    Review {state.held === 1 ? "it" : "them"}
                  </Link>
                </>
              ) : (
                "Nothing needed your review."
              )}
              {state.questions > 0 && (
                <>
                  {" "}
                  {state.questions}{" "}
                  {state.questions === 1 ? "entry was" : "entries were"} missing
                  a required field, so no fact was invented for{" "}
                  {state.questions === 1 ? "it" : "them"}.{" "}
                  <Link className="text-link" href="/career-profile">
                    Add the missing details
                  </Link>
                </>
              )}
            </p>
          </>
        )}
        {state.kind === "failed" && (
          <>
            <p className="text-sm font-semibold text-foreground">
              Some resume facts could not be added automatically.
            </p>
            <p className="mt-0.5 text-xs text-muted">
              {state.applied > 0
                ? `${state.applied} were added before this stopped. `
                : "Nothing was changed. "}
              <Link className="text-link" href="/career-profile/imports">
                Add the rest manually
              </Link>
            </p>
          </>
        )}
      </div>

      {state.kind === "applying" && <Badge tone="primary">Automatic</Badge>}
    </section>
  );
}
