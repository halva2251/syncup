import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft, Plus, Plug, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { ApiError } from "@/lib/api/client";
import { getCurrentUser } from "@/lib/api/me";
import { getMatch } from "@/lib/api/matches";
import { getPublicTasteCard, getTasteProfile } from "@/lib/api/taste";
import { TasteCard } from "@/components/taste/taste-card";
import { TasteActions } from "@/components/taste/taste-actions";
import { ManualObsessionsEditor } from "@/components/taste/manual-obsessions-editor";
import { OwnProfileView } from "@/components/matches/own-profile-view";
import { ButtonLink } from "@/components/ui/button";
import { buildOwnProfileLinks } from "@/lib/constants/profile-links";
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
        user: {
          ...me.user,
          profile_links: buildOwnProfileLinks(me.user.social_links, me.connections),
        },
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
  const hasAnyTasteData = Boolean(
    tasteCard &&
      (Object.keys(tasteCard.services).length > 0 ||
        tasteCard.manual_obsessions.length > 0 ||
        tasteCard.overrides.length > 0),
  );
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || "https://syncup.app";
  const profileUrl = `${appUrl}/feed/${id}`;

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

        {isOwnProfile && tasteCard && tasteCardUser ? (
          <OwnProfileView
            preview={
              <div className="grid items-start gap-6 lg:grid-cols-2">
                <MatchDetail match={match} showCompatibility={false} />
                <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5 sm:p-6">
                  <h2 className="mb-5 text-lg font-semibold text-[var(--color-text-primary)]">
                    Taste card
                  </h2>
                  <TasteCard
                    taste={tasteCard}
                    user={{
                      archetype: tasteCardUser.archetype,
                      vibe_summary: tasteCardUser.vibe_summary,
                      key_themes: tasteCardUser.key_themes,
                    }}
                  />
                </section>
              </div>
            }
            edit={
              <div className="space-y-6">
                <section className="flex flex-col gap-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
                  <div className="space-y-1">
                    <h1 className="text-xl font-semibold text-[var(--color-text-primary)]">
                      Your profile
                    </h1>
                    <p className="text-sm text-[var(--color-text-secondary)]">
                      Manage what people see and how your taste shapes matches.
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <TasteActions
                      hasData={hasAnyTasteData}
                      publicTasteUrl={profileUrl}
                    />
                    <ButtonLink
                      href="/connections"
                      variant="secondary"
                      size="md"
                      className="gap-2"
                    >
                      <Plug className="h-4 w-4" />
                      <span className="hidden sm:inline">Manage services</span>
                    </ButtonLink>
                  </div>
                </section>

                <div className="grid items-start gap-6 lg:grid-cols-2">
                  <MatchDetail
                    match={match}
                    showCompatibility={false}
                    editableLinks
                  />
                  <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5 sm:p-6">
                    <h2 className="mb-5 text-lg font-semibold text-[var(--color-text-primary)]">
                      Taste card
                    </h2>
                    <TasteCard
                      taste={tasteCard}
                      connectedServiceIds={connectedServiceIds}
                      editable
                      showObsessions={false}
                      showOverrides={false}
                      user={{
                        archetype: tasteCardUser.archetype,
                        vibe_summary: tasteCardUser.vibe_summary,
                        key_themes: tasteCardUser.key_themes,
                      }}
                    />
                    <div className="mt-5 border-t border-[var(--color-border-subtle)] pt-5">
                      <ButtonLink
                        href="/connections"
                        variant="secondary"
                        size="md"
                        className="w-full gap-2"
                      >
                        <Plus className="h-4 w-4" />
                        Add services
                      </ButtonLink>
                    </div>
                    <div className="mt-6 space-y-6 border-t border-[var(--color-border-subtle)] pt-6">
                      <section>
                        <ManualObsessionsEditor
                          initialObsessions={tasteCard.manual_obsessions}
                        />
                      </section>

                      <section className="border-t border-[var(--color-border-subtle)] pt-6">
                        <ButtonLink
                          href="/settings/taste"
                          variant="secondary"
                          size="md"
                          className="w-full gap-2"
                        >
                          <SlidersHorizontal className="h-4 w-4" />
                          Edit taste controls
                        </ButtonLink>
                      </section>
                    </div>
                  </section>
                </div>
              </div>
            }
          />
        ) : tasteCard && tasteCardUser ? (
          <div className="grid items-start gap-6 lg:grid-cols-2">
            <MatchDetail match={match} />
            <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5 sm:p-6">
              <h2 className="mb-5 text-lg font-semibold text-[var(--color-text-primary)]">
                Taste card
              </h2>
              <TasteCard
                taste={tasteCard}
                viewerIsOwner={false}
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
