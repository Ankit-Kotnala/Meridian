import { CheckCircle2, Circle, ExternalLink } from "lucide-react";
import Link from "next/link";

import { Alert, Badge, Button, buttonStyles, cn } from "@rezumi/ui";

import type { ResumeBuilderReadinessSnapshot } from "../lib/readiness";

export function ResumeBuilderReadinessPanel({
  onRefresh,
  readiness,
  refreshing,
}: {
  onRefresh: () => void;
  readiness: ResumeBuilderReadinessSnapshot;
  refreshing: boolean;
}) {
  const blocked =
    readiness.status === "blocked" || readiness.status === "error";

  return (
    <section
      aria-labelledby="resume-readiness-heading"
      className="mt-4 rounded-control border border-border bg-surface-subtle p-4"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3
              className="text-sm font-black text-foreground"
              id="resume-readiness-heading"
            >
              Resume source readiness
            </h3>
            <Badge tone={readiness.status === "ready" ? "success" : "warning"}>
              {readiness.status === "ready" ? "Ready" : "Action needed"}
            </Badge>
          </div>
          {readiness.summary && (
            <p className="mt-1 text-sm leading-6 text-muted">
              {readiness.summary}
            </p>
          )}
        </div>
        <Button
          loading={refreshing}
          onClick={onRefresh}
          type="button"
          variant="secondary"
        >
          Refresh readiness
        </Button>
      </div>

      {readiness.status === "error" && (
        <Alert
          className="mt-4"
          title="Source preview unavailable"
          tone="danger"
        >
          {readiness.summary ??
            "Resume Builder could not verify eligible evidence. Try refreshing."}
        </Alert>
      )}

      <ol className="mt-4 space-y-3">
        {readiness.steps.map((step, index) => (
          <li
            className="rounded-control border border-border bg-surface-raised p-3"
            key={step.id}
          >
            <div className="flex items-start gap-3">
              {step.complete ? (
                <CheckCircle2
                  aria-hidden="true"
                  className="mt-0.5 size-4 shrink-0 text-success"
                />
              ) : (
                <Circle
                  aria-hidden="true"
                  className="mt-0.5 size-4 shrink-0 text-muted"
                />
              )}
              <div className="min-w-0 flex-1">
                <p className="text-sm font-bold text-foreground">
                  {index + 1}. {step.title}
                </p>
                <p className="mt-1 text-sm leading-6 text-muted">
                  {step.description}
                </p>
                {!step.complete && (
                  <Link
                    className={cn(
                      buttonStyles.base,
                      buttonStyles.secondary,
                      "mt-3 w-fit",
                    )}
                    href={step.href}
                  >
                    <ExternalLink aria-hidden="true" className="size-4" />
                    {step.actionLabel}
                  </Link>
                )}
              </div>
            </div>
          </li>
        ))}
      </ol>

      {blocked && (
        <p className="mt-4 text-xs leading-5 text-muted">
          Saving facts in Career Profile is not enough on its own. Resume
          Builder only uses evidence you confirm in Evidence Vault.
        </p>
      )}
    </section>
  );
}

export function ResumeSourcePreview({
  headline,
  sourceEvidenceCount,
  bulletCount,
  skillCount,
}: {
  bulletCount: number;
  headline: string | null | undefined;
  skillCount: number;
  sourceEvidenceCount: number;
}) {
  return (
    <section
      aria-labelledby="resume-source-preview-heading"
      className="mt-4 rounded-control border border-border bg-surface-subtle p-4"
    >
      <h3
        className="text-sm font-black text-foreground"
        id="resume-source-preview-heading"
      >
        Eligible source preview
      </h3>
      <p className="mt-1 text-sm leading-6 text-muted">
        This is what Resume Builder can ground in your first draft. It will not
        add facts beyond these eligible evidence sources.
      </p>
      <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-muted">Headline</dt>
          <dd className="font-semibold text-foreground">
            {headline?.trim() || "Not set"}
          </dd>
        </div>
        <div>
          <dt className="text-muted">Eligible evidence</dt>
          <dd className="font-semibold text-foreground">
            {sourceEvidenceCount}
          </dd>
        </div>
        <div>
          <dt className="text-muted">Grounded bullets</dt>
          <dd className="font-semibold text-foreground">{bulletCount}</dd>
        </div>
        <div>
          <dt className="text-muted">Skills in source</dt>
          <dd className="font-semibold text-foreground">{skillCount}</dd>
        </div>
      </dl>
    </section>
  );
}
