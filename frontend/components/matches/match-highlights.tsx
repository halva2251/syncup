import { AppIcon } from "@/components/ui/app-icon";
import { SERVICE_BY_ID } from "@/lib/constants/services";
import { cn } from "@/lib/utils/cn";

interface MatchHighlightsProps {
  highlights: { service: string; item_name: string }[];
  /** Row-capped feed tags vs. fully wrapping tags for detail pages. */
  variant?: "compact" | "detail";
  className?: string;
}

/**
 * Shared-taste highlights between two users. Each item pairs a service brand
 * icon with the item name. The compact feed variant lets items wrap naturally
 * within three rows, while the detail variant shows every item.
 */
export function MatchHighlights({
  highlights,
  variant = "compact",
  className,
}: MatchHighlightsProps) {
  if (highlights.length === 0) return null;

  if (variant === "detail") {
    return (
      <ul className={cn("flex flex-wrap gap-1.5", className)}>
        {highlights.map((h, i) => {
          const service = SERVICE_BY_ID.get(h.service);
          return (
            <li
              key={`${h.service}-${i}`}
              className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-page)] px-2.5 py-1 text-sm text-[var(--color-text-primary)]"
            >
              {service ? (
                <AppIcon
                  brand={service.brand}
                  size="xs"
                  brandColor={`#${service.brand.hex}`}
                  className="!h-4 !w-4"
                />
              ) : null}
              <span>{h.item_name}</span>
            </li>
          );
        })}
      </ul>
    );
  }

  return (
    <ul
      aria-label="Taste you share"
      className={cn("flex max-h-24 flex-wrap gap-1.5 overflow-hidden", className)}
    >
      {highlights.map((h, i) => {
        const service = SERVICE_BY_ID.get(h.service);
        return (
          <li
            key={`${h.service}-${i}`}
            title={`Shared on ${service?.name ?? h.service}`}
            className="flex h-7 max-w-full min-w-0 items-center gap-1.5 rounded-md border border-[var(--color-accent)]/40 bg-[var(--color-accent-soft)] px-2 py-1 text-xs font-medium text-[var(--color-text-primary)]"
          >
            {service ? (
              <AppIcon
                brand={service.brand}
                size="xs"
                brandColor={`#${service.brand.hex}`}
                className="!h-3.5 !w-3.5"
              />
            ) : null}
            <span className="truncate">{h.item_name}</span>
          </li>
        );
      })}
    </ul>
  );
}
