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
          description="Account identity, sign-in, sessions, notifications, consent, and the reusable answers Apply for me copies into a handoff pack. Employment facts stay on your Career Record."
          eyebrow="Your account"
          title="Settings"
        />
        <div className="grid gap-8 lg:grid-cols-[16.5rem_minmax(0,1fr)] lg:items-start">
          <aside className="lg:sticky lg:top-21">
            <SettingsNavigation />
          </aside>
          <div className="min-w-0">{children}</div>
        </div>
      </main>
    </SettingsCapabilitiesProvider>
  );
}
