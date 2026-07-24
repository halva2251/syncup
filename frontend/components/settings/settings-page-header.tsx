import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { AppIcon } from "@/components/ui/app-icon";

interface SettingsPageHeaderProps {
  icon: LucideIcon;
  title: string;
  description: string;
  /** Back-link destination. Defaults to `/settings`. */
  backHref?: string;
  /** Back-link label. Defaults to "Settings". */
  backLabel?: string;
}

export function SettingsPageHeader({
  icon,
  title,
  description,
  backHref = "/settings",
  backLabel = "Settings",
}: SettingsPageHeaderProps) {
  return (
    <div className="space-y-3">
      <Link
        href={backHref}
        className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text-primary)]"
      >
        <ArrowLeft className="h-3.5 w-3.5" strokeWidth={2} />
        {backLabel}
      </Link>
      <div className="space-y-1">
        <div className="flex items-center gap-3">
          <AppIcon icon={icon} size="xs" gradient="brand" />
          <h1 className="text-2xl font-semibold text-[var(--color-text-primary)]">
            {title}
          </h1>
        </div>
        <p className="text-sm text-[var(--color-text-secondary)]">{description}</p>
      </div>
    </div>
  );
}
