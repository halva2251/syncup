import { apiFetch } from "@/lib/api/client";
import type { ManualObsession } from "@/types/api";

export async function listObsessions(): Promise<ManualObsession[]> {
  return apiFetch<ManualObsession[]>("/me/obsessions");
}

export interface CreateObsessionInput {
  category: string;
  name: string;
  external_id?: string | null;
  service?: string | null;
}

export async function createObsession(
  body: CreateObsessionInput
): Promise<ManualObsession> {
  const { category, name, external_id, service } = body;
  return apiFetch<ManualObsession>("/me/obsessions", {
    method: "POST",
    body: JSON.stringify({
      category,
      name: name.trim(),
      weight: 1.0,
      external_id: external_id ?? undefined,
      service: service ?? undefined,
    }),
  });
}

export async function deleteObsession(id: string): Promise<void> {
  return apiFetch<void>(`/me/obsessions/${id}`, {
    method: "DELETE",
  });
}
