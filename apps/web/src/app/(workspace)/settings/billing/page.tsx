import type { Metadata } from "next";

import { BillingSettings } from "@/modules/settings";

export const metadata: Metadata = { title: "Billing settings" };

export default function BillingSettingsPage() {
  return <BillingSettings />;
}
