import type { Metadata } from "next";

import { CareerGrowthView } from "@/modules/career-growth";

export const metadata: Metadata = { title: "Career Growth" };

export default function CareerGrowthPage() {
  return <CareerGrowthView />;
}
