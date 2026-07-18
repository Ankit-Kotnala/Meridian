import type { Metadata } from "next";

import { OnboardingView } from "@/modules/onboarding";

export const metadata: Metadata = { title: "Onboarding" };

export default function OnboardingPage() {
  return <OnboardingView />;
}
