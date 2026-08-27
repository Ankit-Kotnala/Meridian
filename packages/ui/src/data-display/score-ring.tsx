import { cn } from "../internal/cn";

type ScoreRingProps = {
  bandLabel?: string;
  label: string;
  score: number;
  suffix?: string;
  tone?: "primary" | "success" | "warning";
  size?: "sm" | "md" | "lg" | "xl";
};

const toneColor = {
  primary: "var(--primary)",
  success: "var(--score-success, var(--success))",
  warning: "var(--warning-visual)",
} as const;

const sizes = {
  sm: "size-[5.5rem]",
  md: "size-[7.5rem]",
  lg: "size-[9.5rem]",
  xl: "size-[12.5rem]",
} as const;

const strokeWidths = {
  sm: 6,
  md: 7,
  lg: 8,
  xl: 6,
} as const;

const scoreText = {
  sm: "text-[1.625rem]",
  md: "text-[2rem]",
  lg: "text-[2.375rem]",
  xl: "text-[3.75rem]",
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
      <div className="absolute inset-0 grid place-items-center px-2 text-center">
        <div>
          <strong
            className={cn(
              "block font-bold leading-none tracking-[-0.05em] text-foreground",
              scoreText[size],
            )}
          >
            {safeScore}
          </strong>
          {bandLabel ? (
            <span className="mt-1 block text-[0.6875rem] font-semibold text-muted-strong">
              {bandLabel}
            </span>
          ) : (
            <span className="mt-0.5 block text-[0.6875rem] font-semibold text-muted">
              {suffix}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
