import type { Metadata } from "next";

import { JobMatchView } from "@/modules/job-match";
import { RoleReadinessSection } from "@/modules/role-explorer";

export const metadata: Metadata = { title: "Opportunities" };

export default function JobMatchPage() {
  return (
    <main
      className="mx-auto max-w-7xl space-y-10 p-4 sm:p-6 lg:p-8"
      id="main-content"
    >
      <JobMatchView />
      <hr className="border-line" />
      <RoleReadinessSection />
    </main>
  );
}
