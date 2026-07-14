import { cn } from "@/lib/cn";

type ScoreRingProps = {
  label: string;
  score: number;
  suffix?: string;
  tone?: "primary" | "success" | "warning";
  size?: "sm" | "md" | "lg";
};

const toneColor = {
  primary: "#5b46f5",
  success: "#0b9f68",
  warning: "#e59a1f",
} as const;

const sizes = {
  sm: "size-24",
  md: "size-32",
  lg: "size-40",
} as const;

export function ScoreRing({
  label,
  score,
  suffix = "/100",
  tone = "success",
  size = "md",
}: ScoreRingProps) {
  const safeScore = Math.max(0, Math.min(100, score));
  const radius = 42;
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
          stroke="#e9ecf3"
          strokeWidth="8"
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
          strokeWidth="8"
        />
      </svg>
      <div className="absolute text-center">
        <strong className="block text-2xl font-black tracking-[-0.04em] text-foreground">
          {safeScore}
        </strong>
        <span className="text-[0.62rem] font-bold text-muted">{suffix}</span>
      </div>
    </div>
  );
}
