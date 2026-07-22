import { apiFetch } from "@/lib/api/client";
import type { MatchSummary } from "@/types/api";

/** Lightweight match count for dashboard overview cards. */
export async function getMatchSummary(): Promise<MatchSummary> {
  return apiFetch<MatchSummary>("/matches/summary");
}

/* eslint-disable @typescript-eslint/no-explicit-any */
export async function getMatches() {
  return undefined as any;
}

export async function getMatch() {
  return undefined as any;
}
