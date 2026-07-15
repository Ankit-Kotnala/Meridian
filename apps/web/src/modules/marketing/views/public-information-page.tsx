import Link from "next/link";

import { buttonStyles, cn } from "@careeros/ui";

import { SiteFooter } from "@/modules/marketing/components/site-footer";
import { SiteHeader } from "@/modules/marketing/components/site-header";
import type { PublicPageContent } from "@/modules/marketing/content/public-pages";

export function PublicInformationPage({ page }: { page: PublicPageContent }) {
  return (
    <div className="min-h-screen bg-background">
      <SiteHeader />
      <main id="main-content">
        <section className="border-b border-line bg-white py-16 sm:py-20">
          <div className="site-container max-w-4xl">
            <p className="eyebrow">{page.eyebrow}</p>
            <h1 className="balanced mt-3 text-4xl font-black tracking-[-0.045em] sm:text-5xl">
              {page.title}
            </h1>
            <p className="mt-6 max-w-3xl text-lg leading-8 text-muted">
              {page.intro}
            </p>
          </div>
        </section>
        <section className="py-14 sm:py-20">
          <div className="site-container grid max-w-4xl gap-5">
            {page.sections.map(([title, description], index) => (
              <article
                className="surface-card rounded-2xl p-6 sm:p-7"
                key={title}
              >
                <div className="flex items-start gap-4">
                  <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-primary-soft text-xs font-black text-primary">
                    {index + 1}
                  </span>
                  <div>
                    <h2 className="text-lg font-extrabold tracking-[-0.02em]">
                      {title}
                    </h2>
                    <p className="mt-2 leading-7 text-muted">{description}</p>
                  </div>
                </div>
              </article>
            ))}
            <div className="mt-4 flex flex-col gap-3 border-t border-line pt-8 sm:flex-row">
              <Link
                className={cn(buttonStyles.base, buttonStyles.primary)}
                href="/demo/dashboard"
              >
                Explore the fictional demo
              </Link>
              <Link
                className={cn(buttonStyles.base, buttonStyles.secondary)}
                href="/"
              >
                Return to overview
              </Link>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
