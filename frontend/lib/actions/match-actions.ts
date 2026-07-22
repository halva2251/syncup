"use server";

import { revalidatePath } from "next/cache";
import { recomputeMatches } from "@/lib/api/embeddings";
import { ApiError } from "@/lib/api/client";

/**
 * Refresh the current user's match cache. The backend rate-limits this to
 * 1/hour and returns 429 (RATE_LIMITED) when exceeded — surfaced to the caller.
 */
export async function refreshMatchesAction(): Promise<
  { success: true } | { error: string }
> {
  try {
    await recomputeMatches();
    revalidatePath("/feed");
    return { success: true };
  } catch (err) {
    if (err instanceof ApiError) {
      return { error: err.message };
    }
    return { error: "Something went wrong. Please try again." };
  }
}
