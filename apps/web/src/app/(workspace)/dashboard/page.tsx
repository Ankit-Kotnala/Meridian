import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { getCurrentUser } from "@/modules/auth";
import { AutoImportRunner } from "@/modules/career-vault";
import { onboardingIsComplete } from "@/modules/onboarding";
import { dashboardResumeHealth } from "@/modules/resume-health";
import { dashboardSummary, WorkspaceDashboard } from "@/modules/workspace";

export const metadata: Metadata = { title: "Dashboard" };

export default async function DashboardPage() {
  const user = await getCurrentUser();
  if (!user) return null;
  const complete = await onboardingIsComplete();
  if (!complete) redirect("/onboarding");
  const [resumeHealth, summary] = await Promise.all([
    dashboardResumeHealth(),
    dashboardSummary(),
  ]);
  return (
    <WorkspaceDashboard
      autoImport={<AutoImportRunner />}
      displayName={user.displayName}
      onboardingComplete={complete}
      resumeHealth={resumeHealth}
      summary={summary}
      userId={user.id}
    />
  );
}
