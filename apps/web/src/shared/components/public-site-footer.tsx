import Link from "next/link";

import { RezumiLogo } from "@/shared/components/rezumi-logo";

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
      ["Product demo", "/demo/dashboard"],
    ],
  },
] as const;

export function SiteFooter() {
  return (
    <footer className="border-t border-white/10 bg-navy text-white">
      <div className="site-container grid gap-10 py-14 md:grid-cols-[1.35fr_2fr]">
        <div>
          <RezumiLogo inverted />
          <p className="mt-5 max-w-sm text-sm leading-6 text-emerald-50/70">
            Maintain an evidence-backed career record, then use it to create
            grounded applications you control.
          </p>
          <p className="mt-6 text-xs leading-5 text-emerald-100/50">
            Meridian readiness measurements are not employer or applicant tracking
            system scores and do not guarantee outcomes.
          </p>
        </div>
        <nav
          aria-label="Footer navigation"
          className="grid grid-cols-2 gap-8 sm:grid-cols-3"
        >
          {footerGroups.map((group) => (
            <div key={group.title}>
              <h2 className="text-xs font-bold uppercase tracking-[0.12em] text-emerald-100/50">
                {group.title}
              </h2>
              <ul className="mt-4 space-y-3 text-sm">
                {group.links.map(([label, href]) => (
                  <li key={label}>
                    <Link
                      className="inline-flex text-emerald-50/75 transition-[color,transform] hover:translate-x-0.5 hover:text-white hover:underline"
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
        <div className="site-container flex flex-col gap-2 py-5 text-xs text-emerald-100/50 sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} Meridian. Technical product preview.</p>
          <p>Career truth before career polish.</p>
        </div>
      </div>
    </footer>
  );
}
