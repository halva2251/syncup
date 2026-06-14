"use client";

import { useState, useTransition } from "react";
import { X, RotateCcw, AlertCircle } from "lucide-react";
import { excludeItemAction } from "@/lib/actions/taste-actions";

interface ItemExclusionToggleProps {
  itemId: string;
  excluded?: boolean;
  onExcluded?: (itemId: string) => void;
  onIncluded?: (itemId: string) => void;
}

export function ItemExclusionToggle({
  itemId,
  excluded = false,
  onExcluded,
  onIncluded,
}: ItemExclusionToggleProps) {
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  function handleToggle() {
    const next = !excluded;
    setError(null);

    if (next) {
      onExcluded?.(itemId);
    } else {
      onIncluded?.(itemId);
    }

    startTransition(async () => {
      const result = await excludeItemAction(itemId, next);
      if ("error" in result) {
        setError(result.error);
        // Rollback the optimistic update.
        if (next) {
          onIncluded?.(itemId);
        } else {
          onExcluded?.(itemId);
        }
      }
    });
  }

  return (
    <button
      type="button"
      onClick={handleToggle}
      disabled={isPending}
      title={error ?? (excluded ? "Include this item" : "Remove this item")}
      aria-label={error ?? (excluded ? "Include this item" : "Remove this item")}
      className="inline-flex shrink-0 items-center justify-center rounded-md p-1 text-[var(--color-text-tertiary)] transition-colors hover:bg-[var(--color-border-subtle)] hover:text-[var(--color-text-primary)] disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
    >
      {isPending ? (
        <span className="h-3.5 w-3.5 animate-pulse rounded-full bg-current" />
      ) : error ? (
        <AlertCircle className="h-3.5 w-3.5 text-[var(--color-danger)]" />
      ) : excluded ? (
        <RotateCcw className="h-3.5 w-3.5" />
      ) : (
        <X className="h-3.5 w-3.5" />
      )}
    </button>
  );
}
