import { Stepper, type StepperItem } from "@careeros/ui";

import type { OnboardingStep } from "../api/onboarding-api";

const steps: ReadonlyArray<{ label: string; value: OnboardingStep }> = [
  { label: "Profile", value: "profile" },
  { label: "Add resume", value: "resume" },
  { label: "Review details", value: "parsedReview" },
  { label: "Preferences", value: "preferences" },
  { label: "Complete", value: "complete" },
];

export function OnboardingProgress({ current }: { current: OnboardingStep }) {
  const currentIndex = steps.findIndex((step) => step.value === current);
  const items: StepperItem[] = steps.map((step, index) => ({
    label: step.label,
    state:
      index < currentIndex
        ? "complete"
        : index === currentIndex
          ? "current"
          : "upcoming",
  }));
  return (
    <div>
      <p className="mb-3 text-xs font-bold uppercase tracking-[0.08em] text-muted">
        Step {Math.max(1, currentIndex + 1)} of {steps.length}
      </p>
      <Stepper label="Onboarding progress" steps={items} />
    </div>
  );
}
