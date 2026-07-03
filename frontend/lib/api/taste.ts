import { apiFetch } from "@/lib/api/client";
import type { TasteResponse } from "@/types/api";

export async function getTasteProfile(): Promise<TasteResponse> {
  return apiFetch<TasteResponse>("/me/taste");
}
