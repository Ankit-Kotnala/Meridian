import type { Metadata } from "next";

import { SecuritySettings } from "@/modules/settings";

export const metadata: Metadata = { title: "Account security" };

export default function SecuritySettingsPage() {
  return <SecuritySettings />;
}
