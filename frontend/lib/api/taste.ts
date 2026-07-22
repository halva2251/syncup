import { apiFetch } from "@/lib/api/client";
import type { PublicTasteCardResponse, TasteResponse } from "@/types/api";

export async function getTasteProfile(): Promise<TasteResponse> {
  return apiFetch<TasteResponse>("/me/taste");
}

export async function getPublicTasteCard(
  userId: string,
): Promise<PublicTasteCardResponse> {
  return apiFetch<PublicTasteCardResponse>(`/users/${userId}/taste-card`);
}
