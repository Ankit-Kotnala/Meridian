import { Check } from "lucide-react";

import { cn } from "@careeros/ui";

import type { OnboardingStep } from "../api/onboarding-api";

const steps: ReadonlyArray<{ label: string; value: OnboardingStep }> = [
  { label: "Profile", value: "profile" },
  { label: "Resume handoff", value: "resume" },
  { label: "Review handoff", value: "parsedReview" },
  { label: "Preferences", value: "preferences" },
  { label: "Complete", value: "complete" },
];

export function OnboardingProgress({ current }: { current: OnboardingStep }) {
  const currentIndex = steps.findIndex((step) => step.value === current);
  return (
    <nav aria-label="Onboarding progress">
      <p className="mb-3 text-xs font-extrabold uppercase tracking-[0.08em] text-muted">
        Step {Math.max(1, currentIndex + 1)} of {steps.length}
      </p>
      <ol className="grid gap-2 sm:grid-cols-5">
        {steps.map((step, index) => {
          const complete = index < currentIndex;
          const active = index === currentIndex;
          return (
            <li
              aria-current={active ? "step" : undefined}
              className={cn(
                "flex min-h-11 items-center gap-2 rounded-xl border px-3 text-xs font-bold",
                active && "border-primary bg-primary-soft text-primary-strong",
                complete &&
                  "border-emerald-200 bg-success-soft text-success-strong",
                !active && !complete && "border-line bg-white text-muted",
              )}
              key={step.value}
            >
              <span
                aria-hidden="true"
                className={cn(
                  "grid size-5 shrink-0 place-items-center rounded-full border text-[0.65rem]",
                  active && "border-primary bg-primary text-white",
                  complete && "border-success bg-success text-white",
                )}
              >
                {complete ? <Check className="size-3" /> : index + 1}
              </span>
              <span>{step.label}</span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
