import type { ReactNode } from "react";

import { PageHeader } from "@rezumi/ui";

import {
  SettingsCapabilitiesProvider,
  SettingsNavigation,
} from "@/modules/settings";

export default function SettingsLayout({ children }: { children: ReactNode }) {
  return (
    <SettingsCapabilitiesProvider>
      <main className="workspace-page" id="main-content">
        <PageHeader
          description="Manage real account state, preferences, sessions, consent, privacy, connections, and server-reported capability availability."
          eyebrow="Protected account"
          title="Settings"
        />
        <div className="grid gap-7 lg:grid-cols-[13.5rem_minmax(0,1fr)] lg:items-start">
          <SettingsNavigation />
          <div className="min-w-0">{children}</div>
        </div>
      </main>
    </SettingsCapabilitiesProvider>
  );
}
