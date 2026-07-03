"use client";

import { Sparkles, Heart, SlidersHorizontal } from "lucide-react";
import { AppIcon } from "@/components/ui/app-icon";
import { TasteServiceCarousel } from "@/components/taste/taste-service-carousel";
import { CATEGORY_ICONS } from "@/lib/constants/category-icons";
import type { TasteResponse, User } from "@/types/api";

interface TasteCardProps {
  taste: TasteResponse;
  user?: Pick<User, "archetype" | "vibe_summary" | "key_themes">;
}

export function TasteCard({ taste, user }: TasteCardProps) {
  const serviceIds = Object.keys(taste.services);
  const hasAnyData =
    serviceIds.length > 0 ||
    taste.manual_obsessions.length > 0 ||
    taste.overrides.length > 0;

  return (
    <div className="space-y-5">
      {(user?.archetype || user?.vibe_summary) && (
        <div className="rounded-xl border border-[var(--color-border)] bg-gradient-to-br from-[var(--color-accent-soft)] to-[var(--color-bg-card)] p-4">
          <div className="mb-2 flex items-center gap-3">
            <AppIcon icon={Sparkles} size="sm" gradient="brand" />
            <div>
              {user.archetype ? (
                <h3 className="font-semibold text-[var(--color-text-primary)]">
                  {user.archetype}
                </h3>
              ) : null}
              {user.key_themes && user.key_themes.length > 0 ? (
                <p className="text-xs text-[var(--color-text-secondary)]">
                  {user.key_themes.join(" · ")}
                </p>
              ) : null}
            </div>
          </div>
          {user.vibe_summary ? (
            <p className="text-sm leading-relaxed text-[var(--color-text-secondary)]">
              {user.vibe_summary}
            </p>
          ) : null}
        </div>
      )}

      {serviceIds.length > 0 && (
        <TasteServiceCarousel serviceIds={serviceIds} services={taste.services} />
      )}

      {taste.manual_obsessions.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-[var(--color-text-secondary)]">
            Obsessions
          </h3>
          <ul className="flex flex-wrap gap-1.5">
            {taste.manual_obsessions.map((obsession) => {
              const Icon = CATEGORY_ICONS[obsession.category.toLowerCase()] ?? Heart;
              return (
                <li
                  key={obsession.id}
                  className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-page)] px-2.5 py-1 text-sm text-[var(--color-text-primary)]"
                >
                  <Icon className="h-3 w-3 text-[var(--color-text-tertiary)]" />
                  <span>{obsession.name}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {taste.overrides.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-[var(--color-text-secondary)]">
            Preference overrides
          </h3>
          <ul className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
            {taste.overrides.map((override) => (
              <li
                key={override.id}
                className="flex items-center justify-between gap-3 rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-bg-page)] px-3 py-1.5 text-sm"
              >
                <span className="inline-flex items-center gap-2 text-[var(--color-text-primary)]">
                  <SlidersHorizontal className="h-3 w-3 text-[var(--color-text-tertiary)]" />
                  {override.item.name}
                </span>
                <span className="text-xs font-medium text-[var(--color-accent)]">
                  ×{override.boost_multiplier.toFixed(1)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {!hasAnyData && (
        <div className="rounded-xl border border-dashed border-[var(--color-border)] bg-[var(--color-bg-page)] p-6 text-center">
          <p className="text-sm text-[var(--color-text-secondary)]">
            We don&apos;t have enough taste data yet. Connect a service or add a
            few obsessions to build your card.
          </p>
        </div>
      )}
    </div>
  );
}
