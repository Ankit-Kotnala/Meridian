import { cn } from "../internal/cn";

export function Progress({
  className,
  label,
  value,
}: {
  className?: string;
  label: string;
  value: number | null;
}) {
  const bounded = value === null ? null : Math.max(0, Math.min(100, value));
  return (
    <div className={className}>
      <div className="mb-2 flex items-center justify-between gap-3 text-xs">
        <span className="font-bold text-foreground">{label}</span>
        <span className="tabular-nums text-muted">
          {bounded === null ? "In progress" : `${Math.round(bounded)}%`}
        </span>
      </div>
      <div
        aria-label={label}
        aria-valuemax={100}
        aria-valuemin={0}
        {...(bounded === null ? {} : { "aria-valuenow": Math.round(bounded) })}
        className="h-2 overflow-hidden rounded-full bg-surface-inset"
        role="progressbar"
      >
        <div
          className={cn(
            "h-full rounded-full bg-primary transition-[width] duration-300 motion-reduce:transition-none",
            bounded === null &&
              "w-1/3 animate-[pulse_1.4s_ease-in-out_infinite] motion-reduce:animate-none",
          )}
          style={bounded === null ? undefined : { width: `${bounded}%` }}
        />
      </div>
    </div>
  );
}
