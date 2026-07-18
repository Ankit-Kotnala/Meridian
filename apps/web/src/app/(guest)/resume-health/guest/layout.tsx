import type { Metadata } from "next";
import type { ReactNode } from "react";

import { ResumeHealthPublicShell } from "@/modules/resume-health";

export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default function GuestResumeHealthLayout({
  children,
}: {
  children: ReactNode;
}) {
  return <ResumeHealthPublicShell>{children}</ResumeHealthPublicShell>;
}
