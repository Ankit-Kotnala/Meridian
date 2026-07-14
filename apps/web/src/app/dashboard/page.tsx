import type { Metadata } from "next";

import { AppShell } from "@/components/dashboard/app-shell";
import { DashboardOverview } from "@/components/dashboard/dashboard-overview";

export const metadata: Metadata = {
  title: "Fictional dashboard preview",
  description:
    "A fictional-data preview of the CareerOS application shell and dashboard visual system.",
  robots: { index: false, follow: false },
};

export default function DashboardPage() {
  return (
    <AppShell>
      <DashboardOverview />
    </AppShell>
  );
}
