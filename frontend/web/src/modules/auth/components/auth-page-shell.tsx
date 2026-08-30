import { BadgeCheck, FileCheck2, LockKeyhole } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { RezumiLogo } from "@/shared/components/rezumi-logo";

const trustPoints = [
  {
    icon: BadgeCheck,
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
      className="grid min-h-screen bg-background lg:grid-cols-[minmax(0,0.727fr)_minmax(0,1fr)]"
      id="main-content"
    >
      <aside className="relative hidden min-h-screen overflow-hidden bg-[radial-gradient(circle_at_18%_22%,rgba(140,225,212,0.16),transparent_28rem),radial-gradient(circle_at_84%_12%,rgba(255,255,255,0.08),transparent_18rem),radial-gradient(circle_at_48%_116%,rgba(10,96,87,0.34),transparent_24rem),linear-gradient(180deg,#181425_0%,#11101b_52%,#14111f_100%)] px-10 py-10 text-white lg:flex lg:flex-col lg:justify-between xl:px-14">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-[linear-gradient(135deg,rgba(255,255,255,0.03)_0%,transparent_34%,rgba(255,255,255,0.05)_100%)]"
        />
        <RezumiLogo className="relative z-10" href="/" inverted />
        <div className="relative z-10 flex max-w-xl flex-col gap-10">
          <div className="max-w-xl pt-4">
            <p className="text-xs font-bold uppercase tracking-[0.24em] text-[#9fdad1]">
              Career truth before career polish
            </p>
            <h2 className="mt-6 max-w-lg font-display text-[2.55rem] font-semibold leading-[1.08] tracking-[-0.055em] text-white xl:text-[2.9rem]">
              A secure foundation for career information you control.
            </h2>
          </div>

          <ul className="space-y-6">
            {trustPoints.map(
              ({
                description: pointDescription,
                icon: Icon,
                title: pointTitle,
              }) => (
                <li className="flex items-start gap-4" key={pointTitle}>
                  <span className="grid size-12 shrink-0 place-items-center rounded-full border border-white/16 bg-white/5 text-[#98ddd2] shadow-[0_0_0_1px_rgba(255,255,255,0.02)_inset]">
                    <Icon aria-hidden="true" className="size-5" />
                  </span>
                  <span>
                    <span className="block text-[1.025rem] font-semibold text-white">
                      {pointTitle}
                    </span>
                    <span className="mt-1 block max-w-md text-sm leading-6 text-white/68">
                      {pointDescription}
                    </span>
                  </span>
                </li>
              ),
            )}
          </ul>
        </div>
        <p className="relative z-10 max-w-md text-sm leading-6 text-white/58">
          Internal readiness measures are not employer or
          applicant-tracking-system scores and do not guarantee employment
          outcomes.
        </p>
      </aside>

      <section className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[radial-gradient(circle_at_50%_0%,rgba(255,255,255,0.96)_0%,rgba(247,247,243,0.98)_40%,rgba(239,240,236,1)_100%)] px-4 py-10 sm:px-8 lg:px-10">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_14%,rgba(255,255,255,0.78),transparent_42%),linear-gradient(180deg,rgba(255,255,255,0.45)_0%,transparent_28%,transparent_72%,rgba(16,24,40,0.02)_100%)]"
        />
        <div className="relative w-full max-w-[32.75rem]">
          <RezumiLogo className="mb-8 lg:hidden" href="/" />
          <div className="surface-card rounded-[1rem] border border-black/15 bg-white/96 p-6 shadow-[0_14px_28px_-20px_rgba(17,24,39,0.52)] sm:p-10">
            <p className="eyebrow">{eyebrow}</p>
            <h1 className="mt-2 font-display text-[2rem] font-semibold tracking-[-0.055em] text-foreground sm:text-[2.25rem]">
              {title}
            </h1>
            <p className="mt-3 max-w-lg text-[0.98rem] leading-7 text-muted">
              {description}
            </p>
            <div className="mt-8">{children}</div>
          </div>
          <p className="mt-6 text-center text-sm leading-6 text-muted">
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
