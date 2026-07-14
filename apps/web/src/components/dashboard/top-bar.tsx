import { Bell, Command, HelpCircle, Menu, Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { demoFixture } from "@/lib/demo-data";

export function TopBar({ onOpenMenu }: { onOpenMenu: () => void }) {
  return (
    <header className="sticky top-0 z-30 flex h-17 items-center justify-between gap-4 border-b border-line bg-white/95 px-4 backdrop-blur-lg sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <button
          aria-label="Open application navigation"
          className="grid size-10 shrink-0 place-items-center rounded-xl border border-line bg-white text-foreground lg:hidden"
          onClick={onOpenMenu}
          type="button"
        >
          <Menu aria-hidden="true" className="size-5" />
        </button>
        <div className="relative hidden w-[min(34vw,25rem)] sm:block">
          <label className="sr-only" htmlFor="dashboard-search">
            Search the demo workspace
          </label>
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400"
          />
          <input
            className="h-10 w-full rounded-xl border border-line bg-slate-50 pl-10 pr-16 text-sm text-foreground placeholder:text-slate-400"
            id="dashboard-search"
            placeholder="Search fictional workspace…"
            readOnly
            type="search"
          />
          <span
            aria-hidden="true"
            className="absolute right-2.5 top-1/2 flex -translate-y-1/2 items-center gap-1 rounded-md border border-line bg-white px-1.5 py-1 text-[0.58rem] font-bold text-muted"
          >
            <Command className="size-2.5" /> K
          </span>
        </div>
        <Badge className="hidden xl:inline-flex" tone="primary">
          Fictional demo
        </Badge>
      </div>
      <div className="flex items-center gap-1.5">
        <button
          aria-label="Help"
          className="grid size-9 place-items-center rounded-xl text-muted transition hover:bg-slate-100 hover:text-foreground"
          type="button"
        >
          <HelpCircle aria-hidden="true" className="size-4" />
        </button>
        <button
          aria-label="Notifications, 2 fictional items"
          className="relative grid size-9 place-items-center rounded-xl text-muted transition hover:bg-slate-100 hover:text-foreground"
          type="button"
        >
          <Bell aria-hidden="true" className="size-4" />
          <span className="absolute right-2 top-2 size-1.5 rounded-full bg-danger ring-2 ring-white" />
        </button>
        <div className="ml-1 flex items-center gap-2 border-l border-line pl-3">
          <span className="grid size-9 place-items-center rounded-full bg-[linear-gradient(135deg,#5b46f5,#9d7bff)] text-xs font-black text-white shadow-sm">
            {demoFixture.profile.initials}
          </span>
          <div className="hidden leading-tight md:block">
            <p className="text-xs font-extrabold text-foreground">
              {demoFixture.profile.name}
            </p>
            <p className="mt-0.5 text-[0.62rem] text-muted">Demo profile</p>
          </div>
        </div>
      </div>
    </header>
  );
}
