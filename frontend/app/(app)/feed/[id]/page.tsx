import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { ApiError } from "@/lib/api/client";
import { getCurrentUser } from "@/lib/api/me";
import { getMatch } from "@/lib/api/matches";
import { getPublicTasteCard, getTasteProfile } from "@/lib/api/taste";
import { TasteCard } from "@/components/taste/taste-card";
import type { Match, User } from "@/types/api";

export const dynamic = "force-dynamic";

interface FeedDetailPageProps {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({
  params,
}: FeedDetailPageProps): Promise<Metadata> {
  const { id } = await params;
  let name = "Profile";
  try {
    const match = await getMatch(id);
    name = match.user.display_name;
  } catch {
    // Ignore — metadata is best-effort.
  }
  return { title: `${name} · Feed · SyncUp` };
}

export default async function FeedDetailPage({ params }: FeedDetailPageProps) {
  const { id } = await params;

  let match: Match;
  let isOwnProfile = false;
  let tasteCard: Awaited<ReturnType<typeof getTasteProfile>> | null = null;
  let tasteCardUser: Pick<User, "archetype" | "vibe_summary" | "key_themes"> | null = null;
  let connectedServiceIds: string[] = [];
  try {
    const me = await getCurrentUser();
    if (id === me.user.id) {
      isOwnProfile = true;
      tasteCard = await getTasteProfile();
      tasteCardUser = me.user;
      connectedServiceIds = me.connections.map((connection) => connection.service);
      match = {
        user: me.user,
        score: 1,
        breakdown: {},
        shared_highlights: [],
        computed_at: me.user.updated_at,
        matching_mode: "heuristic",
      };
    } else {
      const [otherMatch, publicTasteCard] = await Promise.all([
        getMatch(id),
        getPublicTasteCard(id),
      ]);
      match = otherMatch;
      tasteCard = publicTasteCard.taste;
      tasteCardUser = publicTasteCard.user;
    }
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
    // No match row with this user, or forbidden.
    if (err instanceof ApiError && (err.status === 404 || err.status === 403)) {
      notFound();
    }
    throw err;
  }

  // Lazily import the detail component so the import graph stays clean.
  const { MatchDetail } = await import("@/components/matches/match-detail");

  return (
    <div
      className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10"
    >
      <div className="space-y-6">
        <Link
          href="/feed"
          className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text-primary)]"
        >
          <ArrowLeft className="h-3.5 w-3.5" strokeWidth={2} />
          Feed
        </Link>

        {tasteCard && tasteCardUser ? (
          <div className="grid items-start gap-6 lg:grid-cols-2">
            <MatchDetail match={match} showCompatibility={!isOwnProfile} />
            <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5 sm:p-6">
              <h2 className="mb-5 text-lg font-semibold text-[var(--color-text-primary)]">
                Taste card
              </h2>
              <TasteCard
                taste={tasteCard}
                connectedServiceIds={connectedServiceIds}
                user={{
                  archetype: tasteCardUser.archetype,
                  vibe_summary: tasteCardUser.vibe_summary,
                  key_themes: tasteCardUser.key_themes,
                }}
              />
            </section>
          </div>
        ) : (
          <MatchDetail match={match} />
        )}
      </div>
    </div>
  );
}
