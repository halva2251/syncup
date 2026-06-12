"use server";

import { redirect } from "next/navigation";
import { updateProfile } from "@/lib/api/me";
import { ApiError } from "@/lib/api/client";

export async function updateOnboardingProfile(formData: FormData) {
  const displayName = formData.get("display_name") as string;
  const languagesRaw = formData.get("languages") as string;

  const languages = languagesRaw
    ? languagesRaw
        .split(",")
        .map((lang) => lang.trim())
        .filter(Boolean)
    : null;

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
