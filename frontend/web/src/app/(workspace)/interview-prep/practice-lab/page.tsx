import type { Metadata } from "next";
import { redirect } from "next/navigation";

export const metadata: Metadata = { title: "Skill library" };

export default function InterviewPrepPracticeLabRedirectPage() {
  redirect("/interview-prep/library");
}
