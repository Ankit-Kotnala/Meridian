import {
  AlertCircle,
  ArrowRight,
  BadgeCheck,
  CalendarClock,
  Check,
  ChevronRight,
  CircleDot,
  FileCheck2,
  Plus,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Link from "next/link";

import {
  Badge,
  buttonStyles,
  Card,
  CardHeader,
  cn,
  ScoreBar,
  ScoreRing,
} from "@careeros/ui";

import { MetricCard } from "@/modules/dashboard/components/metric-card";
import { demoFixture } from "@/modules/dashboard/fixtures/demo-data";

const badgeTones = {
  primary: "primary",
  success: "success",
  warning: "warning",
  neutral: "neutral",
} as const;

export function DashboardOverview() {
  return (
    <main className="mx-auto max-w-[98rem] p-4 sm:p-6 lg:p-7" id="main-content">
      <div
        className="mb-5 flex items-start gap-3 rounded-2xl border border-violet-200 bg-[#f4f1ff] p-4 text-[#2d236e]"
        role="note"
      >
        <Sparkles
          aria-hidden="true"
          className="mt-0.5 size-4 shrink-0 text-primary"
        />
        <div className="min-w-0">
          <p className="text-xs font-extrabold uppercase tracking-[0.08em]">
            Fictional demo data · product preview only
          </p>
          <p className="mt-1 text-xs leading-5 text-[#615a85]">
            {demoFixture.fixtureNotice} This preview is not a protected user
            workspace; account data is available only in the signed-in area.
          </p>
        </div>
      </div>

      <header
        className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"
        id="demo-overview"
      >
        <div>
          <p className="text-xs font-bold text-primary">Tuesday, July 14</p>
          <h1 className="mt-1 text-2xl font-black tracking-[-0.035em] text-foreground sm:text-3xl">
            Good morning, {demoFixture.profile.name}.
          </h1>
          <p className="mt-2 text-sm text-muted">
            Here’s the fictional workspace snapshot for today.
          </p>
        </div>
        <button
          className={cn(
            buttonStyles.base,
            buttonStyles.primary,
            "self-start sm:self-auto",
          )}
          type="button"
        >
          <Plus aria-hidden="true" className="size-4" /> New job match
        </button>
      </header>

      <section aria-labelledby="snapshot-heading">
        <h2 className="sr-only" id="snapshot-heading">
          Workspace snapshot
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {demoFixture.metrics.map((metric) => (
            <MetricCard {...metric} key={metric.label} />
          ))}
        </div>
      </section>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1.3fr_0.7fr]">
        <Card id="resume-health">
          <CardHeader
            action={
              <Badge tone="success">
                <BadgeCheck aria-hidden="true" className="size-3" /> Strong
                baseline
              </Badge>
            }
            description="Internal readiness measure · not an employer ATS score"
            title="Resume Health"
          />
          <div className="grid gap-7 p-5 md:grid-cols-[12rem_1fr] md:p-6">
            <div className="flex flex-col items-center justify-center rounded-2xl bg-slate-50 p-5 text-center">
              <ScoreRing
                label="Resume Health Score"
                score={demoFixture.scores.resumeHealth}
                size="lg"
                tone="success"
              />
              <p className="mt-3 text-xs font-extrabold text-success">
                Good foundation
              </p>
              <p className="mt-1 text-[0.68rem] leading-5 text-muted">
                3 focused improvements are ready to review.
              </p>
            </div>
            <div>
              <h3 className="text-xs font-extrabold uppercase tracking-[0.08em] text-muted">
                Score breakdown
              </h3>
              <div className="mt-5 space-y-5">
                {demoFixture.resumeScores.map((item) => (
                  <ScoreBar key={item.label} {...item} />
                ))}
              </div>
            </div>
          </div>
          <div className="border-t border-line px-5 py-4 text-xs leading-5 text-muted">
            CareerOS scores are internal readiness measurements. They are not
            scores provided by an employer or applicant tracking system and do
            not guarantee interviews or employment outcomes.
          </div>
        </Card>

        <Card id="role-readiness">
          <CardHeader
            description={demoFixture.profile.targetRole}
            title="Role readiness"
          />
          <div className="flex flex-col items-center p-5">
            <ScoreRing
              label="Role Readiness"
              score={demoFixture.scores.roleReadiness}
              size="lg"
              tone="warning"
              suffix="%"
            />
            <Badge className="mt-3" tone="warning">
              Developing fit
            </Badge>
          </div>
          <div className="space-y-3 border-t border-line p-5">
            {demoFixture.readiness.map((item) => (
              <div className="flex items-center gap-3" key={item.label}>
                {item.score >= 70 ? (
                  <Check
                    aria-hidden="true"
                    className="size-3.5 shrink-0 text-success"
                    strokeWidth={3}
                  />
                ) : (
                  <AlertCircle
                    aria-hidden="true"
                    className="size-3.5 shrink-0 text-danger"
                  />
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-3 text-xs">
                    <span className="truncate font-semibold text-foreground">
                      {item.label}
                    </span>
                    <span className="font-bold tabular-nums text-muted">
                      {item.score}%
                    </span>
                  </div>
                  <p
                    className={cn(
                      "mt-1 text-[0.62rem] font-semibold",
                      item.score >= 70 ? "text-success" : "text-danger",
                    )}
                  >
                    {item.state}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1fr_0.8fr_1fr]">
        <Card>
          <CardHeader
            action={
              <button
                className="text-xs font-bold text-primary hover:text-primary-strong"
                type="button"
              >
                View all
              </button>
            }
            title="Recent activity"
          />
          <ol className="divide-y divide-line px-5">
            {demoFixture.activities.map((activity) => (
              <li className="flex gap-3 py-4" key={activity.title}>
                <span
                  className={cn(
                    "mt-1 size-2 shrink-0 rounded-full",
                    activity.tone === "success"
                      ? "bg-success"
                      : activity.tone === "warning"
                        ? "bg-[#e59a1f]"
                        : "bg-primary",
                  )}
                />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-extrabold text-foreground">
                    {activity.title}
                  </p>
                  <p className="mt-1 truncate text-[0.68rem] text-muted">
                    {activity.context}
                  </p>
                </div>
                <time className="whitespace-nowrap text-[0.6rem] text-slate-400">
                  {activity.time}
                </time>
              </li>
            ))}
          </ol>
        </Card>

        <Card>
          <CardHeader
            description="Fictional stage counts"
            title="Application pipeline"
          />
          <div className="grid grid-cols-4 gap-2 p-5 text-center">
            {demoFixture.pipeline.map((stage) => (
              <div key={stage.label}>
                <p className="text-2xl font-black tracking-tight text-foreground">
                  {stage.count}
                </p>
                <p className="mt-1 text-[0.62rem] font-semibold text-muted">
                  {stage.label}
                </p>
              </div>
            ))}
          </div>
          <div
            className="flex h-2 gap-1 px-5"
            role="img"
            aria-label="Pipeline summary: 12 saved, 24 applied, 5 interview, 2 offer"
          >
            {demoFixture.pipeline.map((stage) => (
              <span
                className={cn("rounded-full", stage.color)}
                key={stage.label}
                style={{ flexGrow: stage.count }}
              />
            ))}
          </div>
          <div className="p-5">
            <h3 className="text-xs font-extrabold text-foreground">
              This week
            </h3>
            <div className="mt-3 rounded-xl bg-primary-soft p-4">
              <div className="flex items-center gap-2 text-primary">
                <CalendarClock aria-hidden="true" className="size-4" />
                <span className="text-xs font-extrabold">
                  2 interview events
                </span>
              </div>
              <p className="mt-2 text-[0.68rem] leading-5 text-[#655b8f]">
                Review the Resume Defense Map before the fictional Aurora
                Systems conversation.
              </p>
            </div>
          </div>
        </Card>

        <Card id="evidence">
          <CardHeader
            action={
              <ShieldCheck
                aria-label="Evidence controls enabled"
                className="size-4 text-success"
              />
            }
            description="Truth-locked profile status"
            title="Career evidence"
          />
          <div className="grid grid-cols-3 gap-2 p-5 text-center">
            <div className="rounded-xl bg-success-soft p-3">
              <p className="text-xl font-black text-success">
                {demoFixture.evidence.confirmed}
              </p>
              <p className="mt-1 text-[0.6rem] font-bold text-[#087950]">
                Confirmed
              </p>
            </div>
            <div className="rounded-xl bg-warning-soft p-3">
              <p className="text-xl font-black text-warning">
                {demoFixture.evidence.questions}
              </p>
              <p className="mt-1 text-[0.6rem] font-bold text-[#8d5900]">
                Questions
              </p>
            </div>
            <div className="rounded-xl bg-danger-soft p-3">
              <p className="text-xl font-black text-danger">
                {demoFixture.evidence.unsupported}
              </p>
              <p className="mt-1 text-[0.6rem] font-bold text-danger">
                Blocked
              </p>
            </div>
          </div>
          <div className="border-t border-line p-5">
            <div className="flex gap-3 rounded-xl border border-warning/20 bg-warning-soft/60 p-3">
              <CircleDot
                aria-hidden="true"
                className="mt-0.5 size-4 shrink-0 text-warning"
              />
              <div>
                <p className="text-xs font-extrabold text-foreground">
                  One metric needs your answer
                </p>
                <p className="mt-1 text-[0.68rem] leading-5 text-muted">
                  How was the fictional launch result measured?
                </p>
              </div>
            </div>
            <button
              className="mt-4 flex w-full items-center justify-between rounded-xl px-2 py-2 text-xs font-extrabold text-primary hover:bg-primary-soft"
              type="button"
            >
              Review evidence questions{" "}
              <ChevronRight aria-hidden="true" className="size-4" />
            </button>
          </div>
        </Card>
      </div>

      <Card className="mt-5" id="applications">
        <CardHeader
          action={<Badge tone="primary">Fictional pipeline</Badge>}
          description="Applications retain the exact documents and evidence used"
          title="Application workspace"
        />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[44rem] text-left text-xs">
            <caption className="sr-only">
              Fictional job applications and current stages
            </caption>
            <thead className="border-b border-line bg-slate-50 text-[0.62rem] uppercase tracking-[0.08em] text-muted">
              <tr>
                <th className="px-5 py-3 font-extrabold" scope="col">
                  Company
                </th>
                <th className="px-5 py-3 font-extrabold" scope="col">
                  Role
                </th>
                <th className="px-5 py-3 font-extrabold" scope="col">
                  Stage
                </th>
                <th className="px-5 py-3 font-extrabold" scope="col">
                  Next step
                </th>
                <th className="px-5 py-3 text-right font-extrabold" scope="col">
                  <span className="sr-only">Open</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {demoFixture.applications.map((application) => (
                <tr
                  className="transition hover:bg-slate-50/70"
                  key={application.company}
                >
                  <th
                    className="px-5 py-4 font-extrabold text-foreground"
                    scope="row"
                  >
                    {application.company}
                  </th>
                  <td className="px-5 py-4 font-semibold text-muted">
                    {application.role}
                  </td>
                  <td className="px-5 py-4">
                    <Badge tone={badgeTones[application.tone]}>
                      {application.stage}
                    </Badge>
                  </td>
                  <td className="px-5 py-4 text-muted">{application.date}</td>
                  <td className="px-5 py-4 text-right">
                    <button
                      aria-label={`Open fictional ${application.company} application`}
                      className="rounded-lg p-2 text-muted hover:bg-primary-soft hover:text-primary"
                      type="button"
                    >
                      <ChevronRight aria-hidden="true" className="size-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <section
        className="mt-5 rounded-2xl border border-line bg-[linear-gradient(120deg,#0b1d42,#20175a)] p-6 text-white sm:flex sm:items-center sm:justify-between sm:gap-6"
        aria-labelledby="next-step-heading"
      >
        <div className="flex gap-4">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-white/10 text-violet-300">
            <FileCheck2 aria-hidden="true" className="size-5" />
          </span>
          <div>
            <h2 className="font-extrabold" id="next-step-heading">
              Ready to inspect the product foundation?
            </h2>
            <p className="mt-1 text-sm leading-6 text-slate-300">
              Return to the public overview for trust principles, workflow, and
              technical-preview boundaries.
            </p>
          </div>
        </div>
        <Link
          className={cn(
            buttonStyles.base,
            "mt-5 shrink-0 bg-white text-navy hover:bg-violet-50 sm:mt-0",
          )}
          href="/"
        >
          Public overview <ArrowRight aria-hidden="true" className="size-4" />
        </Link>
      </section>
    </main>
  );
}
