import type { Metadata } from "next";

import { ApplicationProfilePanel } from "@/modules/applications";

export const metadata: Metadata = { title: "Application answers" };

export default function ApplicationAnswersSettingsPage() {
  return <ApplicationProfilePanel />;
}
