"use client";

import { useState } from "react";
import { ItemExclusionToggle } from "@/components/taste/item-exclusion-toggle";
import type { TasteItem } from "@/types/api";

interface TasteItemListProps {
  items: TasteItem[];
  emptyMessage?: string;
  rankMode?: "index" | "score" | "rating" | "none";
  getLabel?: (item: TasteItem) => string;
  excludable?: boolean;
}

function formatEngagement(item: TasteItem) {
  if (typeof item.hours === "number") {
    return `${item.hours}h`;
  }
  if (typeof item.play_count === "number") {
    return `${item.play_count} plays`;
  }
  if (typeof item.engagement_score === "number") {
    return `${Math.round(item.engagement_score * 100)}%`;
  }
  return null;
}

function formatRankLabel(
  item: TasteItem,
  index: number,
  rankMode: TasteItemListProps["rankMode"],
) {
  if (rankMode === "none") return null;
  if (rankMode === "rating" && typeof item.rating === "number") {
    return item.rating.toFixed(0);
  }
  if (rankMode === "score" && typeof item.score === "number") {
    return item.score.toFixed(2);
  }
  return String(index + 1);
}

export function TasteItemList({
  items,
  emptyMessage = "No items yet",
  rankMode = "index",
  getLabel,
  excludable = false,
}: TasteItemListProps) {
  const [excludedIds, setExcludedIds] = useState<Set<string>>(
    () => new Set(items.filter((item) => item.excluded).map((item) => item.id)),
  );

  const visibleItems = items.filter((item) => !excludedIds.has(item.id));
  const excludedItems = items.filter((item) => excludedIds.has(item.id));

  if (visibleItems.length === 0 && (!excludable || excludedItems.length === 0)) {
    return (
      <p className="text-sm text-[var(--color-text-tertiary)]">{emptyMessage}</p>
    );
  }

  return (
    <>
      {visibleItems.length > 0 ? (
        <ol className="space-y-1">
          {visibleItems.map((item, index) => {
            const meta = formatEngagement(item);
            const rankLabel = formatRankLabel(item, index, rankMode);
            const label = getLabel ? getLabel(item) : item.name;
            return (
              <li
                key={`${item.id}-${index}`}
                className="flex items-center justify-between gap-3 rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-page)] px-2.5 py-1.5 text-sm"
              >
                <span className="flex items-center gap-2 min-w-0">
                  {rankLabel !== null && (
                    <span className="w-8 shrink-0 text-xs text-[var(--color-text-tertiary)]">
                      {rankLabel}
                    </span>
                  )}
                  <span className="truncate text-[var(--color-text-primary)]">
                    {label}
                  </span>
                </span>
                <span className="inline-flex items-center gap-2 shrink-0">
                  {meta && rankMode !== "score" && rankMode !== "rating" && (
                    <span className="text-xs text-[var(--color-text-tertiary)]">
                      {meta}
                    </span>
                  )}
                  {excludable && (
                    <ItemExclusionToggle
                      itemId={item.id}
                      onExcluded={(itemId) =>
                        setExcludedIds((prev) => new Set(prev).add(itemId))
                      }
                      onIncluded={(itemId) =>
                        setExcludedIds((prev) => {
                          const next = new Set(prev);
                          next.delete(itemId);
                          return next;
                        })
                      }
                    />
                  )}
                </span>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="text-sm text-[var(--color-text-tertiary)]">{emptyMessage}</p>
      )}

      {excludable && excludedItems.length > 0 && (
        <div className="mt-3 border-t border-[var(--color-border-subtle)] pt-3">
          <p className="mb-1.5 text-xs font-medium text-[var(--color-text-secondary)]">
            Add one back
          </p>
          <ol className="space-y-1">
            {excludedItems.map((item) => (
              <li
                key={item.id}
                className="flex items-center justify-between gap-3 rounded-md border border-dashed border-[var(--color-border)] bg-[var(--color-bg-page)] px-2.5 py-1.5 text-sm"
              >
                <span className="min-w-0 truncate text-[var(--color-text-secondary)]">
                  {getLabel ? getLabel(item) : item.name}
                </span>
                <ItemExclusionToggle
                  itemId={item.id}
                  excluded
                  onIncluded={(itemId) =>
                    setExcludedIds((prev) => {
                      const next = new Set(prev);
                      next.delete(itemId);
                      return next;
                    })
                  }
                />
              </li>
            ))}
          </ol>
        </div>
      )}
    </>
  );
}
