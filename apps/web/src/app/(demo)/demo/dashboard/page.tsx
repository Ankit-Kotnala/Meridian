import type { Metadata } from "next";

import { DashboardDemoPage } from "@/modules/dashboard";

export const metadata: Metadata = {
  title: "Fictional dashboard preview",
  description:
    "A fictional-data preview of the Rezumi application shell and dashboard visual system.",
  robots: { index: false, follow: false },
};

export default function DashboardDemoRoute() {
  return <DashboardDemoPage />;
}
