"use server";

import { revalidatePath } from "next/cache";
import {
  updateProfile,
  uploadAvatar,
  type ProfileUpdate,
} from "@/lib/api/me";
import {
  updateDimensions,
  type DimensionWeights,
} from "@/lib/api/dimensions";
import { ApiError } from "@/lib/api/client";

function safeError(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Something went wrong. Please try again.";
}

function parseLanguages(formData: FormData): string[] | null | undefined {
  const raw = formData.get("languages") as string | null;
  if (raw === null) return undefined; // field not submitted — leave unchanged
  if (!raw) return null; // explicit empty — clear
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (Array.isArray(parsed) && parsed.every((v) => typeof v === "string")) {
      return parsed.length > 0 ? parsed : null;
    }
  } catch {
    return undefined;
  }
  return undefined;
}

export async function updateProfileAction(formData: FormData) {
  const displayName = (formData.get("display_name") as string | null)?.trim();
  if (!displayName) {
    return { error: "Display name is required." };
  }
  if (displayName.length > 200) {
    return { error: "Display name must be 200 characters or less." };
  }

  const bio = (formData.get("bio") as string | null)?.trim() || null;
  const discordHandle =
    (formData.get("discord_handle") as string | null)?.trim() || null;
  const languages = parseLanguages(formData);

  const body: ProfileUpdate = {
    display_name: displayName,
    bio,
    discord_handle: discordHandle,
  };
  if (languages !== undefined) body.languages = languages;

  try {
    await updateProfile(body);
    revalidatePath("/settings/profile");
    revalidatePath("/settings");
    return { success: true };
  } catch (err) {
    return { error: safeError(err) };
  }
}

export async function uploadAvatarAction(formData: FormData) {
  const file = formData.get("file") as File | null;
  if (!file || file.size === 0) {
    return { error: "Choose an image file first." };
  }

  try {
    const user = await uploadAvatar(file);
    revalidatePath("/settings/profile");
    revalidatePath("/settings");
    return { success: true, avatar_url: user.avatar_url };
  } catch (err) {
    return { error: safeError(err) };
  }
}

export async function updateMatchableAction(isMatchable: boolean) {
  try {
    await updateProfile({ is_matchable: isMatchable });
    revalidatePath("/settings/privacy");
    revalidatePath("/settings");
    return { success: true, is_matchable: isMatchable };
  } catch (err) {
    return { error: safeError(err) };
  }
}

export async function updateDimensionsAction(weights: DimensionWeights) {
  const hasNonZero = Object.values(weights).some((v) => v > 0);
  if (Object.keys(weights).length === 0 || !hasNonZero) {
    return {
      error:
        "Set at least one service above zero — weights can't all be empty.",
    };
  }

  try {
    await updateDimensions(weights);
    revalidatePath("/settings/dimensions");
    return { success: true };
  } catch (err) {
    return { error: safeError(err) };
  }
}
