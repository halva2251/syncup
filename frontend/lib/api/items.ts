import { apiFetch } from "@/lib/api/client";
import type { TasteItemChoice } from "@/types/api";

export async function listTasteItems(): Promise<TasteItemChoice[]> {
  return apiFetch<TasteItemChoice[]>("/me/items?limit=2000");
}
