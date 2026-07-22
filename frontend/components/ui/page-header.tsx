import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { AppIcon } from "@/components/ui/app-icon";

interface PageHeaderProps {
  /** Lucide icon rendered in an AppIcon tile next to the title. */
  icon: LucideIcon;
  /** Main page title. */
  title: string;
  /** Short description rendered below the title in secondary text. */
  description?: string;
  /** Optional actions (buttons, links) aligned to the right on wide screens. */
  actions?: ReactNode;
}

/**
 * Shared page header: AppIcon + title + description, with an optional
 * actions slot aligned to the right on `sm+` viewports.
 *
 * Rendered as a Server Component so it can accept React node props.
 */
export function PageHeader({
  icon,
  title,
  description,
  actions,
}: PageHeaderProps) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="space-y-1">
        <div className="flex items-center gap-3">
          <AppIcon icon={icon} size="xs" gradient="brand" />
          <h1 className="text-2xl font-semibold text-[var(--color-text-primary)]">
            {title}
          </h1>
        </div>
        {description ? (
          <p className="text-sm text-[var(--color-text-secondary)]">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? (
        <div className="flex items-center gap-2">{actions}</div>
      ) : null}
    </div>
  );
}
