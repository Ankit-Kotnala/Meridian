import { SiteFooter } from "@/shared/components/public-site-footer";
import { SiteHeader } from "@/shared/components/public-site-header";

import { DashboardOverview } from "./dashboard-overview";

export function DashboardDemoPage() {
  return (
    <div className="min-h-screen bg-background">
      <SiteHeader />
      <DashboardOverview />
      <SiteFooter />
    </div>
  );
}
