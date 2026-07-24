import { apiFetch } from "@/lib/api/client";

export type DimensionWeights = Record<string, number>;

export interface DimensionsResponse {
  weights: DimensionWeights;
}

export async function getDimensions(): Promise<DimensionWeights> {
  const data = await apiFetch<DimensionsResponse>("/me/dimensions");
  return data.weights ?? {};
}

export async function updateDimensions(
  weights: DimensionWeights,
): Promise<DimensionWeights> {
  const data = await apiFetch<DimensionsResponse>("/me/dimensions", {
    method: "PATCH",
    body: JSON.stringify({ weights }),
  });
  return data.weights ?? {};
}
