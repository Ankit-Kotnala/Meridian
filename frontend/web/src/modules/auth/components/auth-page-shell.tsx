import { FileCheck2, LockKeyhole, Shield } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { RezumiLogo } from "@/shared/components/rezumi-logo";

const trustPoints = [
  {
    icon: Shield,
    title: "Evidence before claims",
    description:
      "Meridian never fills missing career facts with invented prose.",
  },
  {
    icon: LockKeyhole,
    title: "Private account controls",
    description:
      "Sessions can be reviewed and revoked from your protected settings.",
  },
  {
    icon: FileCheck2,
    title: "You approve material changes",
    description: "Document changes remain visible, reviewable, and reversible.",
  },
] as const;

export function AuthPageShell({
  children,
  description,
  eyebrow,
  title,
}: {
  children: ReactNode;
  description: string;
  eyebrow: string;
  title: string;
}) {
  return (
    <main
      className="grid min-h-screen bg-background lg:grid-cols-[minmax(0,0.72fr)_minmax(0,1fr)]"
      id="main-content"
    >
      <aside className="relative hidden min-h-screen flex-col justify-between bg-[#0f111a] px-10 py-10 text-white lg:flex xl:px-14">
        <RezumiLogo className="relative z-10" href="/" inverted />
        <div className="relative z-10 flex max-w-xl flex-col gap-9">
          <div className="max-w-xl pt-2">
            <p className="text-[0.6875rem] font-bold uppercase tracking-[0.24em] text-[#9aa7a4]">
              Career truth before career polish
            </p>
            <h2 className="auth-display mt-5 max-w-lg text-[2.35rem] font-normal leading-[1.14] tracking-[-0.02em] text-white xl:text-[2.65rem]">
              A secure foundation for career information you control.
            </h2>
          </div>

          <ul className="space-y-5">
            {trustPoints.map(
              ({
                description: pointDescription,
                icon: Icon,
                title: pointTitle,
              }) => (
                <li className="flex items-start gap-3.5" key={pointTitle}>
                  <span className="grid size-10 shrink-0 place-items-center rounded-full border border-white/14 bg-transparent text-[#b8c4c1]">
                    <Icon aria-hidden="true" className="size-[1.05rem]" />
                  </span>
                  <span>
                    <span className="block text-[0.975rem] font-semibold text-white">
                      {pointTitle}
                    </span>
                    <span className="mt-0.5 block max-w-md text-sm leading-6 text-white/60">
                      {pointDescription}
                    </span>
                  </span>
                </li>
              ),
            )}
          </ul>
        </div>
        <p className="relative z-10 max-w-md text-[0.8125rem] leading-6 text-white/45">
          Internal readiness measures are not employer or
          applicant-tracking-system scores and do not guarantee employment
          outcomes.
        </p>
      </aside>

      <section className="flex min-h-screen items-center justify-center px-4 py-10 sm:px-8 lg:px-12">
        <div className="relative w-full max-w-[24.5rem]">
          <RezumiLogo className="mb-8 lg:hidden" href="/" />
          <div className="rounded-[0.75rem] border border-line bg-surface px-6 py-7 shadow-md sm:px-8 sm:py-8">
            <p className="auth-eyebrow">{eyebrow}</p>
            <h1 className="mt-1.5 text-[1.625rem] font-bold tracking-[-0.03em] text-foreground sm:text-[1.75rem]">
              {title}
            </h1>
            <p className="mt-2 text-[0.875rem] leading-6 text-muted">
              {description}
            </p>
            <div className="mt-6">{children}</div>
          </div>
          <p className="mt-5 text-center text-sm leading-6 text-muted">
            Need product context?{" "}
            <Link className="font-semibold text-info-strong" href="/security">
              Read about security and privacy
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
