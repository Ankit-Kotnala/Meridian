"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import {
  InterviewPrepView,
  type InterviewPrepSection,
} from "@/modules/interview-prep";

function sectionFromPath(pathname: string): InterviewPrepSection | null {
  if (pathname === "/interview-prep/practice-lab") return "practice";
  if (pathname === "/interview-prep") return "journey";
  return null;
}

/**
 * Keeps InterviewPrepView mounted across Skill journey / Practice lab so
 * application, story, and session state survive sub-navigation. The section
 * chrome lives in WorkspaceSectionNav, same as Job search.
 */
export default function InterviewPrepLayout({
  children,
}: {
  children: ReactNode;
}) {
  const pathname = usePathname();
  const section = sectionFromPath(pathname);

  if (section) {
    void children;
    return <InterviewPrepView section={section} />;
  }

  return children;
}
