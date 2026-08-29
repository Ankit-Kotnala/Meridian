import type { Metadata } from "next";

import { NetworkingView } from "@/modules/networking";

export const metadata: Metadata = { title: "Networking" };

export default function NetworkingPage() {
  return <NetworkingView />;
}
