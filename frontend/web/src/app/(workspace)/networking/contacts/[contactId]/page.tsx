import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ContactDetailView, isNetworkingId } from "@/modules/networking";

export const metadata: Metadata = { title: "Private contact" };

export default async function ContactPage({
  params,
}: {
  params: Promise<{ contactId: string }>;
}) {
  const { contactId } = await params;
  if (!isNetworkingId(contactId)) notFound();
  return <ContactDetailView contactId={contactId} />;
}
