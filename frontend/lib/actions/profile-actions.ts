"use server";

import { redirect } from "next/navigation";
import { updateProfile } from "@/lib/api/me";
import { ApiError } from "@/lib/api/client";

export async function updateOnboardingProfile(formData: FormData) {
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

  try {
    await updateProfile({ languages });
  } catch (err) {
    if (err instanceof ApiError) {
      return { error: err.message };
    }
    return { error: "Something went wrong. Please try again." };
  }

  redirect("/onboarding/services");
}
