import type { Metadata } from "next";

import { AccountResumeHealthView } from "@/modules/resume-health";

export const metadata: Metadata = { title: "Resume Health" };

export default function AccountResumeHealthPage() {
  return <AccountResumeHealthView />;
}
