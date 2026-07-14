import type { Metadata } from "next";

import { GetStartedView } from "@/modules/auth";

export const metadata: Metadata = { title: "Get started" };

export default function GetStartedPage() {
  return <GetStartedView />;
}
