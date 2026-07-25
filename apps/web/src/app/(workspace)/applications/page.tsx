import type { Metadata } from "next";

import { ApplicationsView } from "@/modules/applications";

export const metadata: Metadata = { title: "Applications" };

export default function ApplicationsPage() {
  return <ApplicationsView />;
}
