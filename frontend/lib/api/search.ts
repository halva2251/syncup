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

function hasItemsShape(data: unknown): data is SearchItemsResponse {
  return (
    typeof data === "object" &&
    data !== null &&
    "items" in data &&
    Array.isArray((data as SearchItemsResponse).items)
  );
}

function extractErrorMessage(body: unknown): string | null {
  if (
    typeof body === "object" &&
    body !== null &&
    "error" in body &&
    body.error !== null &&
    typeof body.error === "object" &&
    "message" in body.error &&
    typeof body.error.message === "string"
  ) {
    return body.error.message;
  }
  return null;
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
    const body = await response.json().catch(() => null);
    const message =
      extractErrorMessage(body) ?? `Search failed (${response.status})`;
    throw new Error(message);
  }

  const data = await response.json().catch(() => null);
  if (!hasItemsShape(data)) {
    throw new Error("Unexpected search response shape");
  }
  return data.items;
}
