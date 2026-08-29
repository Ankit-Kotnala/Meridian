import type { Metadata } from "next";

import { ConnectionSettings } from "@/modules/settings";

export const metadata: Metadata = { title: "Account connections" };

export default function ConnectionSettingsPage() {
  return <ConnectionSettings />;
}
