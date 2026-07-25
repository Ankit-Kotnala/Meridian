import type { Metadata } from "next";

import { AnalyticsView } from "@/modules/analytics";

export const metadata: Metadata = { title: "Career Analytics" };

export default function AnalyticsPage() {
  return <AnalyticsView />;
}
