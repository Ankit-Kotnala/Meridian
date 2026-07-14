import { AppShell } from "@/modules/dashboard/components/app-shell";
import { DashboardOverview } from "@/modules/dashboard/views/dashboard-overview";

export function DashboardDemoPage() {
  return (
    <AppShell>
      <DashboardOverview />
    </AppShell>
  );
}
