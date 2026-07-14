import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { getCurrentUser } from "@/modules/auth";
import { onboardingIsComplete } from "@/modules/onboarding";
import { WorkspaceDashboard } from "@/modules/workspace";

export const metadata: Metadata = { title: "Dashboard" };

export default async function DashboardPage() {
  const user = await getCurrentUser();
  if (!user) return null;
  const complete = await onboardingIsComplete();
  if (!complete) redirect("/onboarding");
  return (
    <WorkspaceDashboard
      displayName={user.displayName}
      onboardingComplete={complete}
    />
  );
}
