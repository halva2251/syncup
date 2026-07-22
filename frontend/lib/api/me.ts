import { apiFetch } from "@/lib/api/client";
import type { MeResponse, User } from "@/types/api";

export async function getCurrentUser(): Promise<MeResponse> {
  return apiFetch<MeResponse>("/me");
}

export interface ProfileUpdate {
  display_name?: string;
  bio?: string | null;
  discord_handle?: string | null;
  avatar_url?: string | null;
  languages?: string[] | null;
  is_matchable?: boolean;
}

export async function updateProfile(body: ProfileUpdate): Promise<User> {
  return apiFetch<User>("/me", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function uploadAvatar(file: File): Promise<User> {
  const formData = new FormData();
  formData.append("file", file);
  return apiFetch<User>("/me/avatar", {
    method: "POST",
    body: formData,
  });
}

export async function updateItemExclusion(
  itemId: string,
  excluded: boolean,
): Promise<void> {
  return apiFetch<void>(`/me/items/${itemId}`, {
    method: "PATCH",
    body: JSON.stringify({ excluded }),
  });
}
