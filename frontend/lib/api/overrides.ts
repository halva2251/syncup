import { apiFetch } from "@/lib/api/client";
import type { PreferenceOverride } from "@/types/api";

export async function listOverrides(): Promise<PreferenceOverride[]> {
  return apiFetch<PreferenceOverride[]>("/me/overrides");
}

export interface CreateOverrideInput {
  item_id: string;
  boost_multiplier: number;
  note?: string | null;
}

export async function createOverride(
  body: CreateOverrideInput,
): Promise<PreferenceOverride> {
  return apiFetch<PreferenceOverride>("/me/overrides", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export interface UpdateOverrideInput {
  boost_multiplier?: number;
  note?: string | null;
}

export async function updateOverride(
  id: string,
  body: UpdateOverrideInput,
): Promise<PreferenceOverride> {
  return apiFetch<PreferenceOverride>(`/me/overrides/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deleteOverride(id: string): Promise<void> {
  await apiFetch<void>(`/me/overrides/${id}`, {
    method: "DELETE",
  });
}
