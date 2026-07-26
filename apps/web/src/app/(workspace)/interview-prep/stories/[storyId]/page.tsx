import type { Metadata } from "next";
import { notFound } from "next/navigation";

import {
  StarStoryDetailView,
  isInterviewPrepId,
} from "@/modules/interview-prep";

export const metadata: Metadata = { title: "STAR story" };

export default async function StarStoryPage({
  params,
}: {
  params: Promise<{ storyId: string }>;
}) {
  const { storyId } = await params;
  if (!isInterviewPrepId(storyId)) notFound();
  return <StarStoryDetailView storyId={storyId} />;
}
