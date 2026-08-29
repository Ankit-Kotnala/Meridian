import type { Metadata } from "next";

import { ChangeStudioView } from "@/modules/change-studio";

export const metadata: Metadata = { title: "Change Studio" };

export default function ChangeStudioPage() {
  return <ChangeStudioView />;
}
