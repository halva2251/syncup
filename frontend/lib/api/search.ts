/** Client-side search API for autocomplete. */

export interface SearchSuggestion {
  name: string;
  service: string;
  item_type: string;
  external_id: string | null;
  extra: Record<string, unknown> | null;
}

export interface SearchItemsResponse {
  items: SearchSuggestion[];
}

export async function searchItems(
  category: string,
  query: string,
  limit = 10
): Promise<SearchSuggestion[]> {
  const params = new URLSearchParams({
    q: query.trim(),
    category,
    limit: String(limit),
  });
  const response = await fetch(`/api/items/search?${params.toString()}`, {
    credentials: "include",
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      error?: { code?: string; message?: string };
    };
    const message = body.error?.message ?? `Search failed (${response.status})`;
    throw new Error(message);
  }

  const data = (await response.json()) as SearchItemsResponse;
  return data.items;
}
