import type { Metadata } from "next";

import { ConsentSettings } from "@/modules/settings";

export const metadata: Metadata = { title: "Consent settings" };

export default function ConsentPage() {
  return <ConsentSettings />;
}
