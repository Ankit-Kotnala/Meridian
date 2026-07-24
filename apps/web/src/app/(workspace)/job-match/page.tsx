import type { Metadata } from "next";

import { JobMatchView } from "@/modules/job-match";

export const metadata: Metadata = { title: "Job Match" };

export default function JobMatchPage() {
  return <JobMatchView />;
}
