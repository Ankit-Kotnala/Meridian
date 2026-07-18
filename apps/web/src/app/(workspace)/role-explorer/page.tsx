import type { Metadata } from "next";

import { RoleExplorerView } from "@/modules/role-explorer";

export const metadata: Metadata = { title: "Role Explorer" };

export default function RoleExplorerPage() {
  return <RoleExplorerView />;
}
