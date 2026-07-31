import { Check } from "lucide-react";

import { cn } from "../internal/cn";

export type StepperItem = {
  description?: string;
  label: string;
  state: "complete" | "current" | "upcoming";
};

export function Stepper({
  className,
  label,
  steps,
}: {
  className?: string;
  label: string;
  steps: readonly StepperItem[];
}) {
  return (
    <nav aria-label={label} className={className}>
      <ol className="grid gap-2 sm:grid-cols-[repeat(auto-fit,minmax(10rem,1fr))]">
        {steps.map((step, index) => (
          <li
            aria-current={step.state === "current" ? "step" : undefined}
            className={cn(
              "relative flex gap-3 rounded-[var(--radius-control)] border px-3 py-3",
              step.state === "current" &&
                "border-primary bg-primary-soft/65 text-primary-strong",
              step.state === "complete" &&
                "border-success/25 bg-success-soft/55 text-success-strong",
              step.state === "upcoming" && "border-line bg-surface text-muted",
            )}
            key={`${step.label}-${index}`}
          >
            <span
              aria-hidden="true"
              className={cn(
                "grid size-6 shrink-0 place-items-center rounded-full border text-[0.6875rem] font-bold",
                step.state === "current" &&
                  "border-primary bg-primary text-white",
                step.state === "complete" &&
                  "border-success bg-success text-white",
                step.state === "upcoming" &&
                  "border-line-strong bg-surface text-muted",
              )}
            >
              {step.state === "complete" ? (
                <Check className="size-3.5" />
              ) : (
                index + 1
              )}
            </span>
            <span className="min-w-0">
              <span className="block text-xs font-bold">{step.label}</span>
              {step.description && (
                <span className="mt-0.5 block text-[0.6875rem] leading-4 opacity-80">
                  {step.description}
                </span>
              )}
            </span>
          </li>
        ))}
      </ol>
    </nav>
  );
}
