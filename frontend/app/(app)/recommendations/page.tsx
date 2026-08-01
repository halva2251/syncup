import type { Metadata } from "next";
import Link from "next/link";
import { Compass, Sparkles } from "lucide-react";
import { redirect } from "next/navigation";
import { ApiError } from "@/lib/api/client";
import {
  getRecommendations,
  RECOMMENDATION_ITEM_TYPES,
  type RecommendationItemType,
} from "@/lib/api/recommendations";
import { SERVICE_BY_ID } from "@/lib/constants/services";
import { AppIcon } from "@/components/ui/app-icon";
import { PageHeader } from "@/components/ui/page-header";
import { BuildTasteVector } from "@/components/recommendations/build-taste-vector";
import { cn } from "@/lib/utils/cn";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Recommendations · SyncUp",
};

const FILTER_LABELS: Record<RecommendationItemType, string> = {
  game: "Games",
  track: "Tracks",
  artist: "Artists",
  film: "Films",
  show: "Shows",
  anime: "Anime",
  manga: "Manga",
  album: "Albums",
  community: "Communities",
};

function isRecommendationItemType(value: string): value is RecommendationItemType {
  return RECOMMENDATION_ITEM_TYPES.includes(value as RecommendationItemType);
}

function typeLabel(type: string) {
  return FILTER_LABELS[type as RecommendationItemType] ?? type;
}

interface RecommendationsPageProps {
  searchParams: Promise<{ item_type?: string }>;
}

export default async function RecommendationsPage({
  searchParams,
}: RecommendationsPageProps) {
  const { item_type } = await searchParams;
  const selectedType = item_type && isRecommendationItemType(item_type)
    ? item_type
    : undefined;
  let recommendations: Awaited<ReturnType<typeof getRecommendations>>["items"] = [];
  let needsTasteVector = false;

  try {
    ({ items: recommendations } = await getRecommendations(selectedType));
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
    if (err instanceof ApiError && err.code === "NO_EMBEDDING_AVAILABLE") {
      needsTasteVector = true;
    } else {
      throw err;
    }
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10">
      <div className="space-y-6">
        <PageHeader
          icon={Compass}
          title="Recommendations"
          description="Find games, music, films, and more that fit your combined taste."
        />

        <nav aria-label="Recommendation type" className="flex flex-wrap gap-2">
          <Link
            href="/recommendations"
            className={cn(
              "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg-page)]",
              !selectedType
                ? "border-[var(--color-accent)] bg-[var(--color-accent-soft)] text-[var(--color-accent)]"
                : "border-[var(--color-border)] bg-[var(--color-bg-card)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-page)] hover:text-[var(--color-text-primary)]",
            )}
          >
            Everything
          </Link>
          {RECOMMENDATION_ITEM_TYPES.map((type) => (
            <Link
              key={type}
              href={`/recommendations?item_type=${type}`}
              className={cn(
                "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg-page)]",
                selectedType === type
                  ? "border-[var(--color-accent)] bg-[var(--color-accent-soft)] text-[var(--color-accent)]"
                  : "border-[var(--color-border)] bg-[var(--color-bg-card)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-page)] hover:text-[var(--color-text-primary)]",
              )}
            >
              {FILTER_LABELS[type]}
            </Link>
          ))}
        </nav>

        {needsTasteVector ? (
          <section className="rounded-xl border border-dashed border-[var(--color-border)] bg-[var(--color-bg-page)] p-10 text-center">
            <Sparkles className="mx-auto h-10 w-10 text-[var(--color-text-tertiary)]" />
            <h2 className="mt-4 text-base font-semibold text-[var(--color-text-primary)]">
              Build your taste vector first
            </h2>
            <p className="mx-auto mt-1.5 max-w-md text-sm text-[var(--color-text-secondary)]">
              SyncUp needs a combined view of your taste before it can find fresh
              recommendations across your favorite domains.
            </p>
            <BuildTasteVector />
          </section>
        ) : recommendations.length === 0 ? (
          <section className="rounded-xl border border-dashed border-[var(--color-border)] bg-[var(--color-bg-page)] p-10 text-center">
            <Compass className="mx-auto h-10 w-10 text-[var(--color-text-tertiary)]" />
            <h2 className="mt-4 text-base font-semibold text-[var(--color-text-primary)]">
              Nothing new to recommend yet
            </h2>
            <p className="mx-auto mt-1.5 max-w-md text-sm text-[var(--color-text-secondary)]">
              Try another category or come back after more people connect and
              sync their libraries.
            </p>
          </section>
        ) : (
          <section aria-label="Recommendations" className="grid gap-4 sm:grid-cols-2">
            {recommendations.map((recommendation) => {
              const service = SERVICE_BY_ID.get(recommendation.service);
              return (
                <article
                  key={`${recommendation.item_type}-${recommendation.service}-${recommendation.item_name}`}
                  className="flex items-start gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5"
                >
                  {service ? (
                    <AppIcon
                      brand={service.brand}
                      size="sm"
                      brandColor={`#${service.brand.hex}`}
                    />
                  ) : (
                    <AppIcon icon={Compass} size="sm" gradient="brand" />
                  )}
                  <div className="min-w-0 flex-1">
                    <h2 className="truncate text-base font-semibold text-[var(--color-text-primary)]">
                      {recommendation.item_name}
                    </h2>
                    <p className="mt-1 text-[13px] text-[var(--color-text-secondary)]">
                      {typeLabel(recommendation.item_type)} on {service?.name ?? recommendation.service}
                    </p>
                    <p className="mt-3 text-xs text-[var(--color-text-tertiary)]">
                      {Math.round(recommendation.similarity_score * 100)}% taste match
                    </p>
                  </div>
                </article>
              );
            })}
          </section>
        )}
      </div>
    </div>
  );
}
