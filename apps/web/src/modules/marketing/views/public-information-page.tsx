import Link from "next/link";

import { buttonStyles, cn } from "@careeros/ui";

import { SiteFooter } from "@/shared/components/public-site-footer";
import { SiteHeader } from "@/shared/components/public-site-header";
import type { PublicPageContent } from "@/modules/marketing/content/public-pages";

export function PublicInformationPage({
  page,
  primaryAction,
  secondaryAction,
}: {
  page: PublicPageContent;
  primaryAction?: { href: string; label: string };
  secondaryAction?: { href: string; label: string };
}) {
  return (
    <div className="min-h-screen bg-background">
      <SiteHeader />
      <main id="main-content">
        <section className="border-b border-line bg-white py-14 sm:py-20">
          <div className="site-container max-w-4xl">
            <p className="eyebrow">{page.eyebrow}</p>
            <h1 className="balanced mt-3 font-display text-4xl font-semibold tracking-[-0.045em] sm:text-5xl">
              {page.title}
            </h1>
            <p className="mt-6 max-w-3xl text-lg leading-8 text-muted">
              {page.intro}
            </p>
          </div>
        </section>
        <section className="py-12 sm:py-20">
          <div className="site-container max-w-4xl">
            <div className="divide-y divide-line border-y border-line">
              {page.sections.map(([title, description], index) => (
                <article
                  className="grid gap-3 py-6 sm:grid-cols-[2.5rem_13rem_minmax(0,1fr)] sm:gap-5 sm:py-8"
                  key={title}
                >
                  <span className="grid size-8 shrink-0 place-items-center rounded-full border border-line-strong bg-white text-xs font-bold text-muted">
                    {index + 1}
                  </span>
                  <h2 className="text-base font-semibold tracking-[-0.02em]">
                    {title}
                  </h2>
                  <p className="leading-7 text-muted">{description}</p>
                </article>
              ))}
            </div>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link
                className={cn(buttonStyles.base, buttonStyles.primary)}
                href={primaryAction?.href ?? "/demo/dashboard"}
              >
                {primaryAction?.label ?? "Explore the fictional demo"}
              </Link>
              <Link
                className={cn(buttonStyles.base, buttonStyles.secondary)}
                href={secondaryAction?.href ?? "/"}
              >
                {secondaryAction?.label ?? "Return to overview"}
              </Link>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
