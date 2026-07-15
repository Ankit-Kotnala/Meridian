import Link from "next/link";
import type { ReactNode } from "react";

import { buttonStyles, cn } from "@careeros/ui";

import { CareerOsLogo } from "@/shared/components/career-os-logo";

export function ResumeHealthPublicShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-line bg-white">
        <div className="site-container flex min-h-17 items-center justify-between gap-4">
          <CareerOsLogo href="/" />
          <div className="flex items-center gap-2">
            <Link
              className={cn(buttonStyles.base, buttonStyles.ghost)}
              href="/resume-health"
            >
              How scoring works
            </Link>
            <Link
              className={cn(buttonStyles.base, buttonStyles.secondary)}
              href="/login?returnTo=%2Fresume-health%2Faccount"
            >
              Sign in
            </Link>
          </div>
        </div>
      </header>
      {children}
      <footer className="mt-14 border-t border-line bg-white">
        <div className="site-container flex flex-col gap-2 py-6 text-xs leading-5 text-muted sm:flex-row sm:justify-between">
          <p>Guest resumes expire automatically and can be deleted sooner.</p>
          <Link className="font-bold text-primary" href="/security">
            Security and privacy
          </Link>
        </div>
      </footer>
    </div>
  );
}
