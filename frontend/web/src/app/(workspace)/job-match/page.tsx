import type { Metadata } from "next";

import { JobMatchView } from "@/modules/job-match";
import { RoleReadinessSection } from "@/modules/role-explorer";

export const metadata: Metadata = { title: "Job search" };

export default function JobMatchPage() {
  // No page gutter here: the tab bar runs full bleed under the top bar, the
  // way the Profile section's sub-navigation does, and each tab panel applies
  // the gutter itself.
  return (
    <main id="main-content">
      <JobMatchView roleMatchingPanel={<RoleReadinessSection />} />
    </main>
  );
}
