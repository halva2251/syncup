import { apiFetch } from "@/lib/api/client";
import type {
  Match,
  MatchListResponse,
  MatchSummary,
} from "@/types/api";

/** Lightweight match count for dashboard overview cards. */
export async function getMatchSummary(): Promise<MatchSummary> {
  return apiFetch<MatchSummary>("/matches/summary");
}

/**
 * Fetch one page of the current user's matches (compatibility, highest first).
 * Keyset-paginated via the opaque `next_cursor` returned by the backend.
 */
export async function getMatches(
  cursor?: string,
  limit = 20,
): Promise<MatchListResponse> {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (cursor) params.set("cursor", cursor);
  return apiFetch<MatchListResponse>(`/matches?${params.toString()}`);
}

/** Fetch the match detail for a specific user (score, breakdown, highlights). */
export async function getMatch(userId: string): Promise<Match> {
  return apiFetch<Match>(`/matches/${userId}`);
}
