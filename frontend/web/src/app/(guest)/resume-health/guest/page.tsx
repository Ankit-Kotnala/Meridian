import type { Metadata } from "next";

import { GuestUploadView } from "@/modules/resume-health";

export const metadata: Metadata = { title: "Guest Resume Health" };

export default function GuestResumeHealthPage() {
  return <GuestUploadView />;
}
