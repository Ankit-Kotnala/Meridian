import type { ReactNode } from "react";

import { SettingsNavigation } from "@/modules/settings";

export default function SettingsLayout({ children }: { children: ReactNode }) {
  return (
    <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
      <header className="mb-6">
        <p className="eyebrow">Protected account</p>
        <h1 className="mt-2 text-2xl font-black tracking-[-0.035em] text-foreground sm:text-3xl">
          Settings
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
          Manage real account state, active sessions, and explicit consent
          choices.
        </p>
      </header>
      <SettingsNavigation />
      <div className="mt-5">{children}</div>
    </main>
  );
}
