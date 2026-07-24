import { apiFetch } from "@/lib/api/client";
import type { RecommendationsResponse } from "@/types/api";

export const RECOMMENDATION_ITEM_TYPES = [
  "game",
  "track",
  "artist",
  "film",
  "show",
  "anime",
  "manga",
  "album",
  "community",
] as const;

export type RecommendationItemType = (typeof RECOMMENDATION_ITEM_TYPES)[number];

/** Fetch cross-domain recommendations, optionally limited to a single item type. */
export function getRecommendations(itemType?: RecommendationItemType) {
  const params = new URLSearchParams({ limit: "20" });
  if (itemType) params.set("item_type", itemType);
  return apiFetch<RecommendationsResponse>(`/me/recommendations?${params}`);
}
