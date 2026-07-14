import {
  ArrowUpRight,
  BriefcaseBusiness,
  FileHeart,
  MessagesSquare,
  Target,
} from "lucide-react";

import { Card, cn } from "@careeros/ui";

import type { DemoMetricTone } from "@/modules/dashboard/fixtures/demo-data";

const metricIcons = {
  "Resume Health": FileHeart,
  "Role Readiness": Target,
  Applications: BriefcaseBusiness,
  Interviews: MessagesSquare,
} as const;

const toneClasses: Record<DemoMetricTone, string> = {
  primary: "bg-primary-soft text-primary",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
};

export function MetricCard({
  label,
  value,
  unit,
  note,
  tone,
}: {
  label: keyof typeof metricIcons;
  value: string;
  unit: string;
  note: string;
  tone: DemoMetricTone;
}) {
  const Icon = metricIcons[label];
  return (
    <Card className="group relative overflow-hidden p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold text-muted">{label}</p>
          <p className="mt-3 flex items-end gap-1 text-3xl font-black tracking-[-0.045em] text-foreground">
            {value}
            {unit && (
              <span className="mb-1 text-xs font-bold tracking-normal text-muted">
                {unit}
              </span>
            )}
          </p>
        </div>
        <span
          className={cn(
            "grid size-9 place-items-center rounded-xl",
            toneClasses[tone],
          )}
        >
          <Icon aria-hidden="true" className="size-4" />
        </span>
      </div>
      <p className="mt-3 flex items-center gap-1.5 text-[0.68rem] font-semibold text-muted">
        <ArrowUpRight aria-hidden="true" className="size-3 text-success" />{" "}
        {note}
      </p>
    </Card>
  );
}
