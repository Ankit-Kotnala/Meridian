import type { Metadata } from "next";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { getCurrentUser, LogoutButton, SessionRecovery } from "@/modules/auth";
import { WorkspaceShell } from "@/modules/workspace";

export const metadata: Metadata = { robots: { index: false, follow: false } };

export default async function ProtectedWorkspaceLayout({
  children,
}: {
  children: ReactNode;
}) {
  const user = await getCurrentUser();
  if (!user) return <SessionRecovery />;
  if (!user.emailVerified) redirect("/verify-email");
  return (
    <WorkspaceShell
      accountActions={<LogoutButton />}
      viewer={{ displayName: user.displayName, email: user.email }}
    >
      {children}
    </WorkspaceShell>
  );
}
