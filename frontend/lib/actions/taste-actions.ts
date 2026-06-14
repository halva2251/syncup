"use server";

import { redirect } from "next/navigation";
import { updateProfile, updateItemExclusion } from "@/lib/api/me";
import { ApiError } from "@/lib/api/client";

export async function enableMatchingAction() {
  try {
    await updateProfile({ is_matchable: true });
  } catch (err) {
    if (err instanceof ApiError) {
      return { error: err.message };
    }
    return { error: "Something went wrong. Please try again." };
  }

  redirect("/home");
}

export async function excludeItemAction(itemId: string, excluded: boolean) {
  try {
    await updateItemExclusion(itemId, excluded);
    return { success: true };
  } catch (err) {
    if (err instanceof ApiError) {
      return { error: err.message };
    }
    return { error: "Something went wrong. Please try again." };
  }
}

export async function buildEmbeddingAction(): Promise<void> {
  // TODO: implement POST /api/embeddings/build on /me/taste page
}

export async function recomputeMatchesAction(): Promise<void> {
  // TODO: implement POST /api/me/recompute on /matches page
}
