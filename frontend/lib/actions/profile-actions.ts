"use server";

import { redirect } from "next/navigation";
import { updateProfile } from "@/lib/api/me";
import { ApiError } from "@/lib/api/client";

export async function updateOnboardingProfile(formData: FormData) {
  const displayName = formData.get("display_name") as string;
  const languagesRaw = formData.get("languages") as string;

  let languages: string[] | null = null;
  if (languagesRaw) {
    try {
      const parsed = JSON.parse(languagesRaw) as unknown;
      if (Array.isArray(parsed) && parsed.every((item) => typeof item === "string")) {
        languages = parsed.length > 0 ? parsed : null;
      }
    } catch {
      return { error: "Invalid languages format." };
    }
  }

  if (!displayName || !displayName.trim()) {
    return { error: "Display name is required." };
  }

  try {
    await updateProfile({
      display_name: displayName.trim(),
      languages,
    });
  } catch (err) {
    if (err instanceof ApiError) {
      return { error: err.message };
    }
    return { error: "Something went wrong. Please try again." };
  }

  redirect("/onboarding/obsessions");
}
