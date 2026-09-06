"use client";

import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";

import {
  RoadmapPanel,
  SkillLibraryPanel,
  type RoadmapSkill,
} from "@/modules/career-growth";
import {
  InterviewPrepView,
  type InterviewPrepSection,
} from "@/modules/interview-prep";

function sectionFromPath(pathname: string): InterviewPrepSection | null {
  if (
    pathname === "/interview-prep/library" ||
    pathname === "/interview-prep/practice-lab"
  ) {
    return "library";
  }
  if (pathname === "/interview-prep") return "journey";
  return null;
}

/**
 * Composes Skill journey and Skill library under Interview Prep chrome.
 * Nested story and session routes render their own pages.
 */
export default function InterviewPrepLayout({
  children,
}: {
  children: ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const section = sectionFromPath(pathname);

  function openLibrary(skill: RoadmapSkill) {
    router.push(
      `/interview-prep/library?skill=${encodeURIComponent(skill.name)}`,
    );
  }

  if (section === "library") {
    void children;
    return <SkillLibraryPanel />;
  }

  if (section === "journey") {
    void children;
    return (
      <InterviewPrepView
        roadmapPanel={
          <RoadmapPanel mode="interview" onOpenLibrary={openLibrary} />
        }
      />
    );
  }

  return children;
}
