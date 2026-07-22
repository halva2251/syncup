import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

interface PageHeaderProps {
  /** Lucide icon shown in the accent color next to the title. */
  icon: LucideIcon;
  /** Main page title. */
  title: string;
  /** Short description rendered below the title in secondary text. */
  description?: string;
  /** Optional actions (buttons, links) aligned to the right on wide screens. */
  actions?: ReactNode;
}

/**
 * Shared page header: accent icon + title + description, with an optional
 * actions slot aligned to the right on `sm+` viewports.
 *
 * Rendered as a Server Component so it can accept React node props.
 */
export function PageHeader({
  icon: Icon,
  title,
  description,
  actions,
}: PageHeaderProps) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <Icon className="h-5 w-5 text-[var(--color-accent)]" />
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
