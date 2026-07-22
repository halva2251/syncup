import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { AppIcon, type AppIconGradient } from "@/components/ui/app-icon";

interface StatCardProps {
  /** Lucide icon rendered in an AppIcon tile. */
  icon: LucideIcon;
  /** AppIcon gradient key. */
  gradient?: AppIconGradient;
  /** Short label above the value. */
  label: string;
  /** The prominent stat value. */
  value: ReactNode;
  /** Optional muted hint rendered below the value. */
  hint?: ReactNode;
}

/**
 * Compact stat/overview card: AppIcon tile + label + value + optional hint.
 *
 * Designed for the top row of a dashboard (per DESIGN.md "Dashboard / Home").
 * Rendered as a Server Component.
 */
export function StatCard({
  icon,
  gradient = "blue",
  label,
  value,
  hint,
}: StatCardProps) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-4 sm:p-5">
      <AppIcon icon={icon} size="sm" gradient={gradient} />
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">
          {label}
        </p>
        <p className="mt-0.5 text-lg font-semibold text-[var(--color-text-primary)]">
          {value}
        </p>
        {hint ? (
          <p className="mt-0.5 text-xs text-[var(--color-text-secondary)]">
            {hint}
          </p>
        ) : null}
      </div>
    </div>
  );
}
