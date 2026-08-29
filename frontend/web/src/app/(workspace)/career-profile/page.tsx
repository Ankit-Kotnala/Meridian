import type { Metadata } from "next";

import { CareerProfileView } from "@/modules/career-vault";

export const metadata: Metadata = { title: "Career Profile" };

export default function CareerProfilePage() {
  return <CareerProfileView />;
}
