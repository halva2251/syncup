import { apiFetch } from "@/lib/api/client";
import type { ManualObsession } from "@/types/api";

export async function listObsessions(): Promise<ManualObsession[]> {
  return apiFetch<ManualObsession[]>("/me/obsessions");
}

export interface CreateObsessionInput {
  category: string;
  name: string;
}

export async function createObsession(
  body: CreateObsessionInput
): Promise<ManualObsession> {
  return apiFetch<ManualObsession>("/me/obsessions", {
    method: "POST",
    body: JSON.stringify({ ...body, weight: 1.0 }),
  });
}

export async function deleteObsession(id: string): Promise<void> {
  return apiFetch<void>(`/me/obsessions/${id}`, {
    method: "DELETE",
  });
}
