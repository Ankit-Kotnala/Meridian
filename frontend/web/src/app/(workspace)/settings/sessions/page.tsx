import type { Metadata } from "next";

import { SessionSettings } from "@/modules/settings";

export const metadata: Metadata = { title: "Session settings" };

export default function SessionsPage() {
  return <SessionSettings />;
}
