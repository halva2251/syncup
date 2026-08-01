"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Search } from "lucide-react";
import { MatchCard } from "@/components/matches/match-card";
import { Button } from "@/components/ui/button";
import type { Match, MatchListResponse } from "@/types/api";

interface MatchListProps {
  /** First page, already fetched server-side. */
  initialItems: Match[];
  /** Cursor for the second page (null = no more pages). */
  initialCursor: string | null;
}

/**
 * Client-side paginated match feed. The first page is fetched server-side and
 * passed in; subsequent pages load on a "Load more" button using the opaque
 * cursor returned by the backend.
 *
 * If the first page is empty (cache miss), the backend kicks off a background
 * refresh. We poll a few times so the user sees results without a manual reload.
 */
export function MatchList({ initialItems, initialCursor }: MatchListProps) {
  const [items, setItems] = useState<Match[]>(initialItems);
  const [cursor, setCursor] = useState<string | null>(initialCursor);
  const [loading, setLoading] = useState(false);
  const [polling, setPolling] = useState(initialItems.length === 0);
  const [error, setError] = useState<string | null>(null);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadMore = useCallback(async () => {
    if (!cursor || loading) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/matches?limit=20&cursor=${encodeURIComponent(cursor)}`, {
        credentials: "include",
      });
      if (!res.ok) throw new Error(`Failed to load more (${res.status})`);
      const data = (await res.json()) as MatchListResponse;
      setItems((prev) => [...prev, ...data.items]);
      setCursor(data.next_cursor);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load more.");
    } finally {
      setLoading(false);
    }
  }, [cursor, loading]);

  // Cache-miss polling: when the server-rendered page is empty, the backend is
  // computing matches in the background. Poll until results appear or we give up.
  useEffect(() => {
    if (!polling) return;
    let attempts = 0;
    const maxAttempts = 5;
    const poll = async () => {
      attempts += 1;
      try {
        const res = await fetch("/api/matches?limit=20", { credentials: "include" });
        if (!res.ok) return;
        const data = (await res.json()) as MatchListResponse;
        if (data.items.length > 0) {
          setItems(data.items);
          setCursor(data.next_cursor);
          setPolling(false);
        } else if (attempts < maxAttempts) {
          pollTimer.current = setTimeout(poll, 3000);
        } else {
          setPolling(false);
        }
      } catch {
        if (attempts < maxAttempts) {
          pollTimer.current = setTimeout(poll, 3000);
        } else {
          setPolling(false);
        }
      }
    };
    pollTimer.current = setTimeout(poll, 3000);
    return () => {
      if (pollTimer.current) clearTimeout(pollTimer.current);
    };
  }, [polling]);

  if (polling) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--color-border)] bg-[var(--color-bg-page)] py-16 text-center">
        <Loader2 className="h-8 w-8 animate-spin text-[var(--color-text-tertiary)]" />
        <p className="mt-3 text-sm text-[var(--color-text-secondary)]">
          Finding people you match with…
        </p>
        <p className="mt-1 text-xs text-[var(--color-text-tertiary)]">
          This can take a few seconds.
        </p>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--color-border)] bg-[var(--color-bg-page)] py-16 text-center">
        <Search className="h-10 w-10 text-[var(--color-text-tertiary)]" />
        <h2 className="mt-4 text-base font-medium text-[var(--color-text-primary)]">
          No matches yet
        </h2>
        <p className="mx-auto mt-1.5 max-w-sm text-sm text-[var(--color-text-secondary)]">
          We couldn&apos;t find any matches right now. Try refreshing, or connect
          more services to improve your taste profile.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <ul className="space-y-3">
        {items.map((match) => (
          <li key={match.user.id}>
            <MatchCard match={match} />
          </li>
        ))}
      </ul>

      {error ? (
        <p className="text-center text-sm text-[var(--color-danger)]">{error}</p>
      ) : null}

      {cursor ? (
        <div className="flex justify-center pt-2">
          <Button
            variant="secondary"
            size="md"
            onClick={loadMore}
            disabled={loading}
            className="gap-2"
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading…
              </>
            ) : (
              "Load more"
            )}
          </Button>
        </div>
      ) : (
        <p className="pt-2 text-center text-xs text-[var(--color-text-tertiary)]">
          You&apos;ve seen everyone for now.
        </p>
      )}
    </div>
  );
}
