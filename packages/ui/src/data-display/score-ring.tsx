import { cn } from "../internal/cn";

type ScoreRingProps = {
  bandLabel?: string;
  label: string;
  score: number;
  suffix?: string;
  tone?: "primary" | "success" | "warning";
  size?: "sm" | "md" | "lg";
};

const toneColor = {
  primary: "var(--primary)",
  success: "var(--success)",
  warning: "var(--warning-visual)",
} as const;

const sizes = {
  sm: "size-24",
  md: "size-32",
  lg: "size-40",
} as const;

const strokeWidths = {
  sm: 7,
  md: 8,
  lg: 9,
} as const;

export function ScoreRing({
  bandLabel,
  label,
  score,
  suffix = "/100",
  tone = "success",
  size = "md",
}: ScoreRingProps) {
  const safeScore = Math.max(0, Math.min(100, score));
  const radius = 42;
  const strokeWidth = strokeWidths[size];
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (safeScore / 100) * circumference;

  return (
    <div
      aria-label={`${label}: ${safeScore}${suffix}`}
      className={cn("relative grid shrink-0 place-items-center", sizes[size])}
      role="img"
    >
      <svg
        aria-hidden="true"
        className="size-full -rotate-90"
        viewBox="0 0 100 100"
      >
        <circle
          cx="50"
          cy="50"
          fill="none"
          r={radius}
          stroke="var(--score-track)"
          strokeWidth={strokeWidth}
        />
        <circle
          cx="50"
          cy="50"
          fill="none"
          r={radius}
          stroke={toneColor[tone]}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          strokeWidth={strokeWidth}
        />
      </svg>
      <div className="absolute text-center">
        <strong
          className={cn(
            "block font-black tracking-[-0.04em] text-foreground",
            size === "sm" ? "text-2xl" : size === "md" ? "text-3xl" : "text-4xl",
          )}
        >
          {safeScore}
        </strong>
        {bandLabel ? (
          <span className="text-[0.65rem] font-bold text-muted">{bandLabel}</span>
        ) : (
          <span className="text-[0.62rem] font-bold text-muted">{suffix}</span>
        )}
      </div>
    </div>
  );
}
