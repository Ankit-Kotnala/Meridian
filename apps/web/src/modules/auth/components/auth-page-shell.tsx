import { BadgeCheck, LockKeyhole, ShieldCheck } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { CareerOsLogo } from "@/shared/components/career-os-logo";

const trustPoints = [
  {
    icon: BadgeCheck,
    title: "Evidence before claims",
    description:
      "CareerOS never fills missing career facts with invented prose.",
  },
  {
    icon: LockKeyhole,
    title: "Private account controls",
    description:
      "Sessions can be reviewed and revoked from your protected settings.",
  },
  {
    icon: ShieldCheck,
    title: "You approve material changes",
    description:
      "Future document changes remain visible, reviewable, and reversible.",
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
      className="grid min-h-screen lg:grid-cols-[minmax(20rem,0.8fr)_minmax(32rem,1.2fr)]"
      id="main-content"
    >
      <aside className="hidden bg-navy px-8 py-10 text-white lg:flex lg:flex-col lg:justify-between xl:px-12">
        <CareerOsLogo href="/" inverted />
        <div className="my-16 max-w-md">
          <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-violet-300">
            Your career. Verified. Elevated.
          </p>
          <h2 className="mt-4 text-3xl font-black leading-tight tracking-[-0.035em]">
            A secure foundation for career information you control.
          </h2>
          <ul className="mt-8 space-y-5">
            {trustPoints.map(
              ({
                description: pointDescription,
                icon: Icon,
                title: pointTitle,
              }) => (
                <li className="flex items-start gap-3" key={pointTitle}>
                  <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-white/10 text-violet-200">
                    <Icon aria-hidden="true" className="size-4" />
                  </span>
                  <span>
                    <span className="block text-sm font-extrabold">
                      {pointTitle}
                    </span>
                    <span className="mt-1 block text-xs leading-5 text-slate-300">
                      {pointDescription}
                    </span>
                  </span>
                </li>
              ),
            )}
          </ul>
        </div>
        <p className="text-xs leading-5 text-slate-400">
          Internal readiness measures are not employer or
          applicant-tracking-system scores and do not guarantee employment
          outcomes.
        </p>
      </aside>

      <section className="flex min-h-screen items-center justify-center bg-background px-4 py-10 sm:px-8">
        <div className="w-full max-w-md">
          <CareerOsLogo className="mb-8 lg:hidden" href="/" />
          <div className="surface-card rounded-2xl p-5 sm:p-8">
            <p className="eyebrow">{eyebrow}</p>
            <h1 className="mt-2 text-2xl font-black tracking-[-0.035em] text-foreground sm:text-3xl">
              {title}
            </h1>
            <p className="mt-3 text-sm leading-6 text-muted">{description}</p>
            <div className="mt-7">{children}</div>
          </div>
          <p className="mt-5 text-center text-xs leading-5 text-muted">
            Need product context?{" "}
            <Link
              className="font-bold text-primary hover:text-primary-strong"
              href="/security"
            >
              Read about security and privacy
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
