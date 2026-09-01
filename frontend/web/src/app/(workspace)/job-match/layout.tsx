"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { JobMatchView, type JobMatchSection } from "@/modules/job-match";
import { RoleReadinessSection } from "@/modules/role-explorer";

function sectionFromPath(pathname: string): JobMatchSection {
  if (pathname.startsWith("/job-match/saved")) return "saved";
  if (pathname.startsWith("/job-match/roles")) return "roles";
  return "search";
}

/**
 * Keeps JobMatchView mounted across Job search / Saved jobs / Role matching so
 * catalog and saved-job state survive sub-navigation. The section chrome itself
 * lives in WorkspaceSectionNav (same component as Profile).
 */
export default function JobMatchLayout({ children }: { children: ReactNode }) {
  // Nested job-match pages render through JobMatchView so catalog/saved-job
  // state survives sub-navigation; the App Router still supplies children.
  void children;
  const pathname = usePathname();
  const section = sectionFromPath(pathname);

  return (
    <main id="main-content">
      <JobMatchView
        roleMatchingPanel={<RoleReadinessSection />}
        section={section}
      />
    </main>
  );
}
