import { Sparkles } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { buttonStyles, cn } from "@rezumi/ui";

import { AccountResumeHealthView } from "@/modules/resume-health";
import { ResumeBuilderView } from "@/modules/resume-builder";

export const metadata: Metadata = { title: "Resumes" };

export default function ResumeStudioPage() {
  return (
    <main className="workspace-page space-y-6" id="main-content">
      <AccountResumeHealthView />
      <ResumeBuilderView />
      <section
        aria-labelledby="change-studio-heading"
        className="rounded-card border border-border bg-surface-raised p-4 shadow-sm sm:p-5"
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
          Review and accept or reject a generated set of resume changes tied to
          a specific job match analysis.
        </p>
        <Link
          className={cn(
            buttonStyles.base,
            buttonStyles.secondary,
            "mt-3 w-fit",
          )}
          href="/change-studio"
        >
          <Sparkles aria-hidden="true" className="size-4" />
          Open Change Studio
        </Link>
      </section>
    </main>
  );
}
