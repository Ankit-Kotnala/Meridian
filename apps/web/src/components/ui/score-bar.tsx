import { cn } from "@/lib/cn";

export function ScoreBar({
  label,
  score,
  tone = "success",
}: {
  label: string;
  score: number;
  tone?: "primary" | "success" | "warning" | "danger";
}) {
  const safeScore = Math.max(0, Math.min(100, score));
  const colors = {
    primary: "bg-primary",
    success: "bg-success",
    warning: "bg-[#e59a1f]",
    danger: "bg-danger",
  };

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-3 text-xs">
        <span className="font-semibold text-foreground">{label}</span>
        <span className="font-bold tabular-nums text-muted">
          {safeScore}/100
        </span>
      </div>
      <div
        aria-label={`${label}: ${safeScore} out of 100`}
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={safeScore}
        className="h-1.5 overflow-hidden rounded-full bg-slate-200"
        role="progressbar"
      >
        <div
          className={cn("h-full rounded-full", colors[tone])}
          style={{ width: `${safeScore}%` }}
        />
      </div>
    </div>
  );
}
