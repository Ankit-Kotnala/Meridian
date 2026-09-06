"use client";

import { RefreshCcw } from "lucide-react";
import { useRouter } from "next/navigation";
import { type ReactNode } from "react";

import { Button, PageHeader } from "@rezumi/ui";

export function InterviewPrepView({
  roadmapPanel,
}: {
  roadmapPanel: ReactNode;
}) {
  const router = useRouter();

  return (
    <main className="workspace-page space-y-6" id="main-content">
      <PageHeader
        actions={
          <Button onClick={() => router.refresh()} variant="secondary">
            <RefreshCcw aria-hidden="true" className="size-4" />
            Refresh
          </Button>
        }
        description="Evidence-backed skill development for your target role, with a mapped library of free courses, paid courses, and readable study notes for every stored skill."
        eyebrow="Interview Prep"
        title="Interview readiness workspace"
      />

      <section aria-labelledby="personalized-roadmap-heading">
        <h2 className="sr-only" id="personalized-roadmap-heading">
          Personalized interview roadmap
        </h2>
        {roadmapPanel}
      </section>
    </main>
  );
}
