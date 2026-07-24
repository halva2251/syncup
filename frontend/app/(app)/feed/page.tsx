import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Compass } from "lucide-react";
import { ApiError } from "@/lib/api/client";
import { getCurrentUser } from "@/lib/api/me";
import { getMatches } from "@/lib/api/matches";
import { PageHeader } from "@/components/ui/page-header";
import { MatchList } from "@/components/matches/match-list";
import { FeedActions } from "./feed-actions";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Feed · SyncUp",
};

export default async function FeedPage() {
  let isMatchable = true;
  let initialItems: Awaited<ReturnType<typeof getMatches>>["items"] = [];
  let initialCursor: string | null = null;

  try {
    const [me, matchesPage] = await Promise.all([
      getCurrentUser(),
      getMatches(undefined, 20),
    ]);
    isMatchable = me.user.is_matchable;
    initialItems = matchesPage.items;
    initialCursor = matchesPage.next_cursor;
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
    // NOT_MATCHABLE (403) — handled below; anything else surfaces.
    if (err instanceof ApiError && err.status === 403) {
      isMatchable = false;
    } else {
      throw err;
    }
  }

  if (!isMatchable) {
    return (
      <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10">
        <div className="space-y-6">
          <PageHeader
            icon={Compass}
            title="Feed"
            description="Discover people whose taste matches yours."
          />
          <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--color-border)] bg-[var(--color-bg-page)] py-16 text-center">
            <Compass className="h-10 w-10 text-[var(--color-text-tertiary)]" />
            <h2 className="mt-4 text-base font-medium text-[var(--color-text-primary)]">
              Matching is turned off
            </h2>
            <p className="mx-auto mt-1.5 max-w-sm text-sm text-[var(--color-text-secondary)]">
              Enable matching in privacy settings so others can find you and you
              can discover them.
            </p>
            <FeedActions disabled />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10">
      <div className="space-y-6">
        <PageHeader
          icon={Compass}
          title="Feed"
          description="Discover people whose taste matches yours, ranked by compatibility."
          actions={<FeedActions />}
        />
        <MatchList initialItems={initialItems} initialCursor={initialCursor} />
      </div>
    </div>
  );
}
