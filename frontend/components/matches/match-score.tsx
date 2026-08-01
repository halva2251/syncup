import { cn } from "@/lib/utils/cn";

interface MatchScoreProps {
  /** Compatibility score in the range [0, 1]. */
  score: number;
  /** Compact pill (cards) vs. larger block (detail). */
  variant?: "compact" | "detail";
  className?: string;
}

function scoreBucket(score: number): "high" | "mid" | "low" {
  if (score >= 0.75) return "high";
  if (score >= 0.5) return "mid";
  return "low";
}

const bucketClasses: Record<
  ReturnType<typeof scoreBucket>,
  { badge: string; bar: string }
> = {
  high: {
    badge:
      "bg-[var(--color-tag-green-bg)] text-[var(--color-tag-green-text)]",
    bar: "bg-[var(--color-success)]",
  },
  mid: {
    badge:
      "bg-[var(--color-tag-yellow-bg)] text-[var(--color-tag-yellow-text)]",
    bar: "bg-[var(--color-warning)]",
  },
  low: {
    badge:
      "bg-[var(--color-tag-purple-bg)] text-[var(--color-tag-purple-text)]",
    bar: "bg-[var(--color-text-tertiary)]",
  },
};

/**
 * Compatibility score display. Compact variant renders a colored pill;
 * detail variant adds a label and a proportional progress bar.
 */
export function MatchScore({ score, variant = "compact", className }: MatchScoreProps) {
  const pct = Math.round(Math.max(0, Math.min(1, score)) * 100);
  const bucket = scoreBucket(score);
  const classes = bucketClasses[bucket];

  if (variant === "compact") {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold",
          classes.badge,
          className,
        )}
      >
        {pct}% match
      </span>
    );
  }

  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">
          Compatibility
        </span>
        <span className="text-sm font-semibold text-[var(--color-text-primary)]">
          {pct}%
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--color-border-subtle)]">
        <div
          className={cn("h-full rounded-full transition-all", classes.bar)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
