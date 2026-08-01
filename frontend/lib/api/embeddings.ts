import { apiFetch } from "@/lib/api/client";

/**
 * Force-refresh the current user's match cache (and vibe synthesis if an LLM key
 * is configured). Rate-limited to 1/hour server-side; returns 204 immediately
 * while the work runs in the background.
 */
export async function recomputeMatches(): Promise<void> {
  await apiFetch<void>("/me/recompute", { method: "POST" });
}
