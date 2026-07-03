"use server";

import { revalidatePath } from "next/cache";
import { createObsession, deleteObsession } from "@/lib/api/obsessions";
import { ApiError } from "@/lib/api/client";

const CATEGORIES = new Set([
  "game",
  "music",
  "film",
  "book",
  "show",
  "anime",
  "manga",
  "community",
  "other",
]);

function validateName(name: string): string | null {
  const trimmed = name.trim();
  if (!trimmed) return "Name is required.";
  if (trimmed.length > 200) return "Name must be 200 characters or less.";
  return null;
}

function parseCategory(value: string): string | null {
  try {
    const parsed = JSON.parse(value);
    if (Array.isArray(parsed) && parsed.length > 0 && typeof parsed[0] === "string") {
      return parsed[0];
    }
  } catch {
    // fall through
  }
  return value || null;
}

export async function createObsessionAction(formData: FormData) {
  const categoryRaw = formData.get("category") as string;
  const category = parseCategory(categoryRaw);
  const name = formData.get("name") as string;
  const externalId = formData.get("name_external_id") as string | null;
  const service = formData.get("name_service") as string | null;

  if (!category || !CATEGORIES.has(category)) {
    return { error: "Please select a valid category." };
  }

  const nameError = validateName(name);
  if (nameError) {
    return { error: nameError };
  }

  try {
    const obsession = await createObsession({
      category,
      name: name.trim(),
      external_id: externalId || null,
      service: service || null,
    });
    revalidatePath("/onboarding/obsessions");
    return { obsession };
  } catch (err) {
    if (err instanceof ApiError) {
      return { error: err.message };
    }
    return { error: "Something went wrong. Please try again." };
  }
}

export async function deleteObsessionAction(id: string) {
  try {
    await deleteObsession(id);
  } catch (err) {
    if (err instanceof ApiError) {
      return { error: err.message };
    }
    return { error: "Something went wrong. Please try again." };
  }

  revalidatePath("/onboarding/obsessions");
  return { success: true };
}
