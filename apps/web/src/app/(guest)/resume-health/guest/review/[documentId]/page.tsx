import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { CanonicalReviewView, isResourceId } from "@/modules/resume-health";

export const metadata: Metadata = { title: "Review parsed guest resume" };

export default async function GuestReviewPage({
  params,
}: {
  params: Promise<{ documentId: string }>;
}) {
  const { documentId } = await params;
  if (!isResourceId(documentId)) notFound();
  return <CanonicalReviewView access="guest" documentId={documentId} />;
}
