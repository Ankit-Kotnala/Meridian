import Link from "next/link";

import { CareerOsLogo } from "@/shared/components/career-os-logo";

const footerGroups = [
  {
    title: "Product",
    links: [
      ["Overview", "/product"],
      ["Features", "/features"],
      ["Resume Health", "/resume-health"],
      ["Pricing", "/pricing"],
    ],
  },
  {
    title: "Trust",
    links: [
      ["Security & privacy", "/security"],
      ["Scoring methodology", "/methodology"],
      ["Responsible AI", "/responsible-ai"],
      ["Privacy policy", "/privacy"],
    ],
  },
  {
    title: "Company",
    links: [
      ["About", "/about"],
      ["Contact", "/contact"],
      ["Terms", "/terms"],
      ["Product demo", "/dashboard"],
    ],
  },
] as const;

export function SiteFooter() {
  return (
    <footer className="border-t border-white/10 bg-navy text-white">
      <div className="site-container grid gap-10 py-14 md:grid-cols-[1.35fr_2fr]">
        <div>
          <CareerOsLogo inverted />
          <p className="mt-5 max-w-sm text-sm leading-6 text-slate-300">
            Build a verified career profile once, then use it to create
            stronger, evidence-backed applications.
          </p>
          <p className="mt-6 text-xs leading-5 text-slate-400">
            CareerOS readiness measurements are not employer or applicant
            tracking system scores and do not guarantee outcomes.
          </p>
        </div>
        <nav
          aria-label="Footer navigation"
          className="grid grid-cols-2 gap-8 sm:grid-cols-3"
        >
          {footerGroups.map((group) => (
            <div key={group.title}>
              <h2 className="text-xs font-extrabold uppercase tracking-[0.12em] text-slate-400">
                {group.title}
              </h2>
              <ul className="mt-4 space-y-3 text-sm">
                {group.links.map(([label, href]) => (
                  <li key={label}>
                    <Link
                      className="text-slate-200 transition hover:text-white"
                      href={href}
                    >
                      {label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
      </div>
      <div className="border-t border-white/10">
        <div className="site-container flex flex-col gap-2 py-5 text-xs text-slate-400 sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} CareerOS. Phase 0 product preview.</p>
          <p>Your career. Verified. Elevated.</p>
        </div>
      </div>
    </footer>
  );
}
