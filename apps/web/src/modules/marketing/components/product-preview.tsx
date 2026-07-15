import {
  ArrowUpRight,
  Check,
  FileCheck2,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import { Badge, ScoreRing } from "@careeros/ui";

import { productPreviewFixture } from "@/modules/marketing/fixtures/product-preview-data";

export function ProductPreview() {
  return (
    <div
      className="relative mx-auto w-full max-w-[37rem]"
      aria-label="CareerOS fictional dashboard preview"
    >
      <div
        aria-hidden="true"
        className="absolute -inset-10 -z-10 rounded-full bg-primary/10 blur-3xl"
      />
      <div className="overflow-hidden rounded-[1.6rem] border border-slate-200 bg-white shadow-[0_28px_90px_rgba(20,30,72,.17)]">
        <div className="flex items-center justify-between border-b border-line bg-slate-50/80 px-5 py-3">
          <div className="flex items-center gap-2">
            <span className="size-2.5 rounded-full bg-[#ff756d]" />
            <span className="size-2.5 rounded-full bg-[#ffc556]" />
            <span className="size-2.5 rounded-full bg-[#5acb8a]" />
          </div>
          <Badge tone="primary">Fictional demo</Badge>
        </div>
        <div className="grid min-h-[25rem] grid-cols-[4.25rem_1fr] sm:grid-cols-[8.5rem_1fr]">
          <div className="bg-navy p-3 text-white sm:p-4">
            <div className="flex items-center gap-2 text-[0.65rem] font-extrabold sm:text-xs">
              <Sparkles className="size-4 text-violet-300" />
              <span className="hidden sm:inline">CareerOS</span>
            </div>
            <div className="mt-7 space-y-2">
              {["Overview", "Resume health", "Evidence", "Applications"].map(
                (label, index) => (
                  <div
                    className={`rounded-lg px-2 py-2 text-[0.58rem] sm:text-[0.65rem] ${index === 0 ? "bg-primary text-white" : "text-slate-400"}`}
                    key={label}
                  >
                    <span className="hidden sm:inline">{label}</span>
                    <span className="block h-2 w-7 rounded bg-current opacity-50 sm:hidden" />
                  </div>
                ),
              )}
            </div>
          </div>
          <div className="min-w-0 bg-[#f8f9fc] p-4 sm:p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[0.58rem] font-bold text-muted">
                  Good morning, {productPreviewFixture.profile.firstName}
                </p>
                <p className="mt-1 text-sm font-black tracking-tight text-foreground sm:text-base">
                  Your career command center
                </p>
              </div>
              <span className="grid size-8 place-items-center rounded-full bg-primary-soft text-[0.6rem] font-black text-primary">
                {productPreviewFixture.profile.initials}
              </span>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-line bg-white p-3.5 shadow-sm">
                <div className="flex items-center gap-2 text-[0.62rem] font-bold text-muted">
                  <FileCheck2 className="size-3.5 text-success" /> Resume health
                </div>
                <div className="mt-3 flex items-center gap-3">
                  <ScoreRing
                    label="Resume Health"
                    score={productPreviewFixture.resumeHealth.score}
                    size="sm"
                  />
                  <div className="hidden min-w-0 sm:block">
                    <p className="text-xs font-extrabold text-foreground">
                      {productPreviewFixture.resumeHealth.summary}
                    </p>
                    <p className="mt-1 text-[0.6rem] leading-4 text-muted">
                      {productPreviewFixture.resumeHealth.focusedImprovements}{" "}
                      focused improvements identified.
                    </p>
                  </div>
                </div>
              </div>
              <div className="rounded-xl border border-line bg-white p-3.5 shadow-sm">
                <div className="flex items-center justify-between text-[0.62rem] font-bold text-muted">
                  Readiness breakdown <ArrowUpRight className="size-3" />
                </div>
                <div className="mt-4 space-y-4">
                  {productPreviewFixture.readinessBreakdown.map((item) => (
                    <div key={item.label}>
                      <div className="mb-1.5 flex justify-between gap-2 text-[0.56rem] font-semibold">
                        <span className="truncate">{item.label}</span>
                        <span>{item.score}</span>
                      </div>
                      <div className="h-1 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className={`h-full rounded-full ${item.color}`}
                          style={{ width: `${item.score}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="mt-3 rounded-xl border border-line bg-white p-3.5 shadow-sm">
              <div className="flex items-center justify-between">
                <p className="text-[0.65rem] font-extrabold">
                  Evidence-backed next steps
                </p>
                <ShieldCheck className="size-4 text-success" />
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-3">
                {productPreviewFixture.nextSteps.map((item) => (
                  <div
                    className="flex gap-1.5 rounded-lg bg-slate-50 p-2 text-[0.55rem] font-semibold text-muted"
                    key={item}
                  >
                    <Check className="size-3 shrink-0 text-success" /> {item}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
      <div className="absolute -bottom-7 -left-3 hidden items-center gap-3 rounded-2xl border border-line bg-white p-3 shadow-xl sm:flex">
        <span className="grid size-9 place-items-center rounded-xl bg-success-soft text-success">
          <ShieldCheck className="size-4" />
        </span>
        <div>
          <p className="text-[0.6rem] font-bold text-muted">Truth confidence</p>
          <p className="text-xs font-black text-foreground">
            Claims linked to evidence
          </p>
        </div>
      </div>
    </div>
  );
}
