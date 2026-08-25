import { Sparkles } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { buttonStyles, cn } from "@rezumi/ui";

import { AccountResumeHealthView } from "@/modules/resume-health";
import { ResumeBuilderView } from "@/modules/resume-builder";

export const metadata: Metadata = { title: "Resume Studio" };

export default function ResumeStudioPage() {
  return (
    <main
      className="mx-auto max-w-7xl space-y-10 p-4 sm:p-6 lg:p-8"
      id="main-content"
    >
      <AccountResumeHealthView />
      <hr className="border-line" />
      <ResumeBuilderView />
      <hr className="border-line" />
      <section
        aria-labelledby="change-studio-heading"
        className="rounded-lg border border-line bg-surface p-4 shadow-sm"
      >
        <div className="flex items-center gap-2">
          <Sparkles aria-hidden="true" className="size-5 text-primary" />
          <h2
            className="text-lg font-black text-foreground"
            id="change-studio-heading"
          >
            Change Studio
          </h2>
        </div>
        <p className="mt-1 text-sm text-muted">
          Review and accept or reject a generated set of resume changes tied
          to a specific job match analysis.
        </p>
        <Link
          className={cn(buttonStyles.base, buttonStyles.secondary, "mt-3 w-fit")}
          href="/change-studio"
        >
          <Sparkles aria-hidden="true" className="size-4" />
          Open Change Studio
        </Link>
      </section>
    </main>
  );
}
