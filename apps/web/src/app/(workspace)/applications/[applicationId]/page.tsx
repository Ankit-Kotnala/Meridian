import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ApplicationDetailView, isApplicationId } from "@/modules/applications";

export const metadata: Metadata = { title: "Application details" };

export default async function ApplicationDetailPage({
  params,
}: {
  params: Promise<{ applicationId: string }>;
}) {
  const { applicationId } = await params;
  if (!isApplicationId(applicationId)) notFound();
  return <ApplicationDetailView applicationId={applicationId} />;
}
